import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../api/client';
import { format } from 'date-fns';
import { toZonedTime } from 'date-fns-tz';

const SettingsPage = () => {
  const queryClient = useQueryClient();
  const [newCompany, setNewCompany] = useState('');
  const [notes, setNotes] = useState('');
  const [selectedInterval, setSelectedInterval] = useState<number>(10);
  const [selectedBatchSize, setSelectedBatchSize] = useState<number>(20);
  const [processingResult, setProcessingResult] = useState<any>(null);

  const { data: whitelist, isLoading } = useQuery({
    queryKey: ['whitelist'],
    queryFn: () => apiClient.getWhitelist(),
  });

  const addMutation = useMutation({
    mutationFn: (params: { companyName: string; notes?: string }) =>
      apiClient.addToWhitelist(params.companyName, params.notes),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['whitelist'] });
      setNewCompany('');
      setNotes('');
    },
  });

  const removeMutation = useMutation({
    mutationFn: (companyId: number) => apiClient.removeFromWhitelist(companyId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['whitelist'] });
    },
  });

  const { data: scheduleConfig, isLoading: scheduleLoading } = useQuery({
    queryKey: ['scheduleConfig'],
    queryFn: () => apiClient.getScheduleConfig(),
  });

  useEffect(() => {
    if (scheduleConfig) {
      setSelectedInterval(scheduleConfig.interval_minutes);
      setSelectedBatchSize(scheduleConfig.batch_size || 20);
    }
  }, [scheduleConfig]);

  const updateScheduleMutation = useMutation({
    mutationFn: (params: { intervalMinutes?: number; batchSize?: number }) =>
      apiClient.updateScheduleConfig(params.intervalMinutes, params.batchSize),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scheduleConfig'] });
      queryClient.invalidateQueries({ queryKey: ['summaryStats'] });
    },
  });

  const runProcessingMutation = useMutation({
    mutationFn: () => apiClient.runProcessing(),
    onSuccess: (data) => {
      setProcessingResult(data);
      queryClient.invalidateQueries({ queryKey: ['summaryStats'] });
      queryClient.invalidateQueries({ queryKey: ['processingRuns'] });
      setTimeout(() => setProcessingResult(null), 10000);
    },
    onError: (error: any) => {
      setProcessingResult({
        status: 'error',
        message: error.response?.data?.detail || error.message || 'Failed to run processing',
      });
      setTimeout(() => setProcessingResult(null), 10000);
    },
  });

  const handleAdd = () => {
    if (newCompany.trim()) {
      addMutation.mutate({
        companyName: newCompany.trim(),
        notes: notes.trim() || undefined,
      });
    }
  };

  const handleRemove = (companyId: number) => {
    if (window.confirm('Are you sure you want to remove this company from the whitelist?')) {
      removeMutation.mutate(companyId);
    }
  };

  const handleUpdateSchedule = () => {
    const intervalChanged = selectedInterval !== scheduleConfig?.interval_minutes;
    const batchChanged = selectedBatchSize !== scheduleConfig?.batch_size;

    if (intervalChanged || batchChanged) {
      updateScheduleMutation.mutate({
        intervalMinutes: intervalChanged ? selectedInterval : undefined,
        batchSize: batchChanged ? selectedBatchSize : undefined,
      });
    }
  };

  // Slider positions map to these minute values
  const intervalSteps = [5, 10, 15, 30, 60, 120];
  const batchSizeSteps = [10, 20, 30, 50, 75, 100];

  const intervalToSliderPos = (minutes: number): number => {
    const idx = intervalSteps.indexOf(minutes);
    return idx >= 0 ? idx : 1; // default to 10 min position
  };

  const sliderPosToInterval = (pos: number): number => {
    return intervalSteps[pos] || 10;
  };

  const batchToSliderPos = (size: number): number => {
    const idx = batchSizeSteps.indexOf(size);
    return idx >= 0 ? idx : 1; // default to 20 position
  };

  const sliderPosToBatch = (pos: number): number => {
    return batchSizeSteps[pos] || 20;
  };

  const getIntervalLabel = (minutes: number): string => {
    if (minutes === 60) return 'Every hour';
    if (minutes === 120) return 'Every 2 hours';
    return `Every ${minutes} minutes`;
  };

  const getBatchLabel = (size: number): string => {
    return `${size} emails per run`;
  };

  // Convert UTC to CST (America/Chicago)
  const formatDateCST = (dateString: string) => {
    const utcString = dateString.endsWith('Z') || dateString.includes('+') ? dateString : dateString + 'Z';
    const date = new Date(utcString);
    const cstDate = toZonedTime(date, 'America/Chicago');
    return format(cstDate, 'MMM d, yyyy h:mm a');
  };

  const hasChanges =
    selectedInterval !== scheduleConfig?.interval_minutes ||
    selectedBatchSize !== scheduleConfig?.batch_size;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
        <p className="mt-1 text-sm text-gray-600">
          Manage processing schedule, batch size, and whitelist
        </p>
      </div>

      {/* Processing Schedule Configuration */}
      <div className="bg-white shadow rounded-lg">
        <div className="px-4 py-5 sm:p-6">
          <h2 className="text-lg font-medium text-gray-900 mb-4">
            Processing Schedule
          </h2>
          <p className="text-sm text-gray-600 mb-4">
            Configure how often and how many emails are processed each run.
          </p>

          {scheduleLoading ? (
            <div className="flex justify-center py-4">
              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary-600"></div>
            </div>
          ) : (
            <div className="space-y-6">
              {/* Interval Slider */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Processing Interval
                </label>
                <div className="max-w-md">
                  <input
                    type="range"
                    min={0}
                    max={intervalSteps.length - 1}
                    step={1}
                    value={intervalToSliderPos(selectedInterval)}
                    onChange={(e) => setSelectedInterval(sliderPosToInterval(Number(e.target.value)))}
                    className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-primary-600"
                  />
                  <div className="flex justify-between mt-1">
                    {intervalSteps.map((val) => (
                      <span
                        key={val}
                        className={`text-xs ${
                          val === selectedInterval ? 'text-primary-600 font-semibold' : 'text-gray-400'
                        }`}
                      >
                        {val === 120 ? '2h' : val === 60 ? '60m' : `${val}m`}
                      </span>
                    ))}
                  </div>
                  <p className="mt-2 text-sm font-medium text-gray-900">
                    {getIntervalLabel(selectedInterval)}
                  </p>
                </div>
              </div>

              {/* Batch Size Slider */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Batch Size
                </label>
                <div className="max-w-md">
                  <input
                    type="range"
                    min={0}
                    max={batchSizeSteps.length - 1}
                    step={1}
                    value={batchToSliderPos(selectedBatchSize)}
                    onChange={(e) => setSelectedBatchSize(sliderPosToBatch(Number(e.target.value)))}
                    className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-primary-600"
                  />
                  <div className="flex justify-between mt-1">
                    {batchSizeSteps.map((val) => (
                      <span
                        key={val}
                        className={`text-xs ${
                          val === selectedBatchSize ? 'text-primary-600 font-semibold' : 'text-gray-400'
                        }`}
                      >
                        {val}
                      </span>
                    ))}
                  </div>
                  <p className="mt-2 text-sm font-medium text-gray-900">
                    {getBatchLabel(selectedBatchSize)}
                  </p>
                </div>
              </div>

              {scheduleConfig?.last_updated && (
                <div className="text-sm text-gray-500">
                  Last updated: {formatDateCST(scheduleConfig.last_updated)} CST
                  {scheduleConfig.updated_by && ` by ${scheduleConfig.updated_by}`}
                </div>
              )}

              <button
                onClick={handleUpdateSchedule}
                disabled={!hasChanges || updateScheduleMutation.isPending}
                className="px-4 py-2 bg-primary-600 text-white rounded-md text-sm font-medium hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {updateScheduleMutation.isPending ? 'Updating...' : 'Update Settings'}
              </button>

              {updateScheduleMutation.isSuccess && (
                <div className="text-sm text-green-600">
                  Settings updated successfully!
                </div>
              )}

              {updateScheduleMutation.isError && (
                <div className="text-sm text-red-600">
                  Failed to update settings. Please try again.
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Manual Processing */}
      <div className="bg-white shadow rounded-lg">
        <div className="px-4 py-5 sm:p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-2">
            Manual Processing
          </h3>
          <p className="text-sm text-gray-600 mb-4">
            Trigger email processing manually to fetch and classify new emails from your inbox.
            This will process up to {selectedBatchSize} emails.
          </p>
          <button
            onClick={() => runProcessingMutation.mutate()}
            disabled={runProcessingMutation.isPending}
            className="px-4 py-2 bg-primary-600 text-white rounded-md text-sm font-medium hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {runProcessingMutation.isPending ? (
              <span className="flex items-center">
                <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Processing...
              </span>
            ) : (
              'Run Email Processing'
            )}
          </button>

          {/* Processing Result */}
          {processingResult && (
            <div
              className={`mt-4 p-4 rounded-md ${
                processingResult.status === 'success'
                  ? 'bg-green-50 text-green-800 border border-green-200'
                  : processingResult.status === 'info'
                  ? 'bg-blue-50 text-blue-800 border border-blue-200'
                  : 'bg-red-50 text-red-800 border border-red-200'
              }`}
            >
              <p className="text-sm font-medium">{processingResult.message}</p>
              {processingResult.summary?.imported && (
                <div className="mt-2 text-sm">
                  <p>Processed {processingResult.summary.total_emails} emails</p>
                  <p>Found {processingResult.summary.interview_requests} interview requests</p>
                </div>
              )}
              {processingResult.duration_seconds && (
                <p className="mt-1 text-xs">
                  Duration: {processingResult.duration_seconds.toFixed(1)}s
                </p>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Whitelist Management */}
      <div className="bg-white shadow rounded-lg">
        <div className="px-4 py-5 sm:p-6">
          <h2 className="text-lg font-medium text-gray-900 mb-4">
            Whitelist Management
          </h2>
          <p className="text-sm text-gray-600 mb-4">
            Companies on the whitelist are never moved or deleted, regardless of AI classification.
          </p>

          {/* Add Company Form */}
          <div className="border border-gray-300 rounded-lg p-4 mb-6">
            <h3 className="text-sm font-medium text-gray-900 mb-3">
              Add Company to Whitelist
            </h3>
            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Company Name
                </label>
                <input
                  type="text"
                  value={newCompany}
                  onChange={(e) => setNewCompany(e.target.value)}
                  placeholder="e.g., Acme Corporation"
                  className="block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Notes (optional)
                </label>
                <input
                  type="text"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Reason for adding to whitelist"
                  className="block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                />
              </div>
              <button
                onClick={handleAdd}
                disabled={!newCompany.trim() || addMutation.isPending}
                className="w-full sm:w-auto px-4 py-2 bg-primary-600 text-white rounded-md text-sm font-medium hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {addMutation.isPending ? 'Adding...' : 'Add to Whitelist'}
              </button>
            </div>
          </div>

          {/* Whitelist Table */}
          {isLoading ? (
            <div className="flex justify-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
            </div>
          ) : !whitelist || whitelist.length === 0 ? (
            <p className="text-sm text-gray-500 text-center py-8">
              No companies in whitelist
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-300">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">
                      Company Name
                    </th>
                    <th className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">
                      Added By
                    </th>
                    <th className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">
                      Date Added
                    </th>
                    <th className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">
                      Notes
                    </th>
                    <th className="relative py-3.5 pl-3 pr-4 sm:pr-6">
                      <span className="sr-only">Actions</span>
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200 bg-white">
                  {whitelist.map((company) => (
                    <tr key={company.id}>
                      <td className="whitespace-nowrap px-3 py-4 text-sm font-medium text-gray-900">
                        {company.company_name}
                      </td>
                      <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                        {company.added_by}
                      </td>
                      <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                        {format(new Date(company.added_date), 'MMM d, yyyy')}
                      </td>
                      <td className="px-3 py-4 text-sm text-gray-500 max-w-xs truncate">
                        {company.notes || '-'}
                      </td>
                      <td className="relative whitespace-nowrap py-4 pl-3 pr-4 text-right text-sm font-medium sm:pr-6">
                        <button
                          onClick={() => handleRemove(company.id)}
                          disabled={removeMutation.isPending}
                          className="text-red-600 hover:text-red-900 disabled:opacity-50"
                        >
                          Remove
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default SettingsPage;
