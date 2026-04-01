import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { apiClient } from '../api/client';
import type { InterviewEventRecord } from '../types';

const TYPE_STYLES: Record<string, string> = {
  interview_request: 'bg-blue-100 text-blue-800',
  phone_screen: 'bg-green-100 text-green-800',
  client_screen: 'bg-purple-100 text-purple-800',
  technical_interview: 'bg-yellow-100 text-yellow-800',
  cancelled: 'bg-red-100 text-red-800',
  rescheduled: 'bg-orange-100 text-orange-800',
  job_machine: 'bg-indigo-100 text-indigo-800',
};

const TYPE_LABELS: Record<string, string> = {
  interview_request: 'Interview Request',
  phone_screen: 'Phone Screen',
  client_screen: 'Client Screen',
  technical_interview: 'Technical Interview',
  cancelled: 'Cancelled',
  rescheduled: 'Rescheduled',
  job_machine: 'Job Machine',
};

const NOTIF_STYLES: Record<string, string> = {
  sent: 'bg-green-100 text-green-800',
  approved: 'bg-blue-100 text-blue-800',
  draft: 'bg-yellow-100 text-yellow-800',
  failed: 'bg-red-100 text-red-800',
  rejected: 'bg-gray-100 text-gray-600',
};

const NOTIF_LABELS: Record<string, string> = {
  sent: 'Notified',
  approved: 'Approved',
  draft: 'Draft',
  failed: 'Send Failed',
  rejected: 'Rejected',
};

type FilterTab = 'all' | 'notified' | 'pending';

const InterviewEventsReportPage = () => {
  const [activeTab, setActiveTab] = useState<FilterTab>('all');
  const [search, setSearch] = useState('');

  const { data: events, isLoading } = useQuery({
    queryKey: ['interviewEvents'],
    queryFn: () => apiClient.getInterviewEvents(),
    staleTime: 0,
    refetchOnMount: 'always',
  });

  const getTypeStyle = (type?: string) =>
    type ? (TYPE_STYLES[type] || 'bg-gray-100 text-gray-800') : 'bg-gray-100 text-gray-800';

  const getTypeLabel = (type?: string) =>
    type ? (TYPE_LABELS[type] || type) : 'N/A';

  const getNotifStyle = (status?: string) =>
    status ? (NOTIF_STYLES[status] || 'bg-gray-100 text-gray-800') : 'bg-gray-50 text-gray-400';

  const getNotifLabel = (status?: string) =>
    status ? (NOTIF_LABELS[status] || status) : 'No Draft';

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return '—';
    return dateStr;
  };

  const formatSentAt = (isoStr?: string) => {
    if (!isoStr) return '—';
    const d = new Date(isoStr.endsWith('Z') ? isoStr : isoStr + 'Z');
    return d.toLocaleString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric',
      hour: 'numeric', minute: '2-digit', hour12: true,
    });
  };

  const filtered = (events || []).filter((e) => {
    // Tab filter
    if (activeTab === 'notified' && e.notification_status !== 'sent') return false;
    if (activeTab === 'pending' && !['draft', 'approved'].includes(e.notification_status || '')) return false;

    // Search filter
    if (search) {
      const q = search.toLowerCase();
      return (
        (e.student_name || '').toLowerCase().includes(q) ||
        (e.company_name || '').toLowerCase().includes(q) ||
        (e.position_title || '').toLowerCase().includes(q)
      );
    }
    return true;
  });

  const notifiedCount = (events || []).filter((e) => e.notification_status === 'sent').length;
  const pendingCount = (events || []).filter((e) =>
    ['draft', 'approved'].includes(e.notification_status || '')
  ).length;

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2 text-sm text-gray-500 mb-1">
            <Link to="/" className="hover:text-primary-600">Dashboard</Link>
            <span>›</span>
            <span className="text-gray-700">Interview Events Report</span>
          </div>
          <h1 className="text-2xl font-bold text-gray-900">Interview Events Report</h1>
          <p className="mt-1 text-sm text-gray-600">
            All interview events detected and processed, with student and notification status.
          </p>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="bg-white shadow rounded-lg p-5">
          <p className="text-sm font-medium text-gray-500">Total Events</p>
          <p className="mt-1 text-3xl font-bold text-gray-900">{events?.length || 0}</p>
        </div>
        <div
          className="bg-white shadow rounded-lg p-5 cursor-pointer hover:shadow-md transition-shadow"
          onClick={() => setActiveTab('notified')}
        >
          <p className="text-sm font-medium text-gray-500">Students Notified</p>
          <p className="mt-1 text-3xl font-bold text-green-600">{notifiedCount}</p>
          <p className="mt-1 text-xs text-primary-600">Click to filter</p>
        </div>
        <div
          className="bg-white shadow rounded-lg p-5 cursor-pointer hover:shadow-md transition-shadow"
          onClick={() => setActiveTab('pending')}
        >
          <p className="text-sm font-medium text-gray-500">Pending Notification</p>
          <p className="mt-1 text-3xl font-bold text-yellow-600">{pendingCount}</p>
          <p className="mt-1 text-xs text-primary-600">Click to filter</p>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white shadow rounded-lg p-4 flex flex-col sm:flex-row items-start sm:items-center gap-4">
        {/* Tab filters */}
        <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
          {(['all', 'notified', 'pending'] as FilterTab[]).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-4 py-1.5 text-sm font-medium rounded-md transition-colors ${
                activeTab === tab
                  ? 'bg-white text-gray-900 shadow-sm'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              {tab === 'all' ? 'All' : tab === 'notified' ? 'Notified' : 'Pending'}
            </button>
          ))}
        </div>

        {/* Search */}
        <input
          type="text"
          placeholder="Search student, company, position..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="flex-1 px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
        />

        <span className="text-sm text-gray-500 whitespace-nowrap">
          {filtered.length} result{filtered.length !== 1 ? 's' : ''}
        </span>
      </div>

      {/* Table */}
      <div className="bg-white shadow rounded-lg overflow-hidden">
        {filtered.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Student
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Type
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Company
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Position
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Interview Date
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Format
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Notification
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Notified At
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Sent To
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {filtered.map((event: InterviewEventRecord) => (
                  <tr key={event.event_id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 whitespace-nowrap">
                      <div className="text-sm font-medium text-gray-900">
                        {event.student_name || 'Unknown'}
                      </div>
                      {event.student_email && (
                        <div className="text-xs text-gray-400">{event.student_email}</div>
                      )}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      <span className={`px-2 py-1 text-xs font-medium rounded ${getTypeStyle(event.interview_type)}`}>
                        {getTypeLabel(event.interview_type)}
                      </span>
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">
                      {event.company_name || '—'}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-900 max-w-xs truncate">
                      {event.position_title || '—'}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-700">
                      {event.interview_date ? (
                        <span>
                          {formatDate(event.interview_date)}
                          {event.interview_time && (
                            <span className="ml-1 text-gray-400">
                              {event.interview_time}
                              {event.interview_timezone && ` ${event.interview_timezone}`}
                            </span>
                          )}
                        </span>
                      ) : '—'}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-600 capitalize">
                      {event.interview_format || '—'}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      <span className={`px-2 py-1 text-xs font-medium rounded ${getNotifStyle(event.notification_status)}`}>
                        {getNotifLabel(event.notification_status)}
                      </span>
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-xs text-gray-500">
                      {formatSentAt(event.notified_at)}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-xs text-gray-500">
                      {event.recipient_email || '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-16">
            <svg className="mx-auto h-12 w-12 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
            </svg>
            <h3 className="mt-2 text-sm font-medium text-gray-900">No events found</h3>
            <p className="mt-1 text-sm text-gray-500">
              {search || activeTab !== 'all'
                ? 'Try adjusting your filters.'
                : 'No interview events have been processed yet.'}
            </p>
            {(search || activeTab !== 'all') && (
              <button
                onClick={() => { setSearch(''); setActiveTab('all'); }}
                className="mt-3 text-sm text-primary-600 hover:text-primary-800"
              >
                Clear filters
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default InterviewEventsReportPage;
