import { useState, Fragment } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../api/client';
import { format } from 'date-fns';
import { toZonedTime } from 'date-fns-tz';
import InterviewChecklist from '../components/InterviewChecklist';
import type { InterviewRequest } from '../types';

const TYPE_STYLES: Record<string, string> = {
  'interview_request': 'bg-blue-100 text-blue-800',
  'phone_screen': 'bg-green-100 text-green-800',
  'client_screen': 'bg-purple-100 text-purple-800',
  'technical_interview': 'bg-yellow-100 text-yellow-800',
  'cancelled': 'bg-red-100 text-red-800',
  'rescheduled': 'bg-orange-100 text-orange-800',
  'job_machine': 'bg-indigo-100 text-indigo-800',
};

const TYPE_LABELS: Record<string, string> = {
  'interview_request': 'Interview Request',
  'phone_screen': 'Phone Screen',
  'client_screen': 'Client Screen',
  'technical_interview': 'Technical Interview',
  'cancelled': 'Cancelled',
  'rescheduled': 'Rescheduled',
  'job_machine': 'Job Machine',
};

const InterviewsPage = () => {
  const [expandedInterviewId, setExpandedInterviewId] = useState<number | null>(null);

  const { data: interviews, isLoading } = useQuery({
    queryKey: ['interviews'],
    queryFn: () => apiClient.getInterviewRequests(200, 0),
    staleTime: 0,
    refetchOnMount: 'always',
  });

  const { data: countData } = useQuery({
    queryKey: ['interviewCount'],
    queryFn: () => apiClient.getInterviewCount(),
  });

  // Convert UTC to CST (America/Chicago)
  // Backend sends UTC timestamps without Z suffix, so we append it
  const formatDateCST = (dateString: string) => {
    const utcString = dateString.endsWith('Z') || dateString.includes('+') ? dateString : dateString + 'Z';
    const date = new Date(utcString);
    const cstDate = toZonedTime(date, 'America/Chicago');
    return format(cstDate, 'MMM d, yyyy h:mm a');
  };

  const toggleExpand = (interviewId: number) => {
    setExpandedInterviewId(expandedInterviewId === interviewId ? null : interviewId);
  };

  const getTypeStyle = (interviewType?: string) => {
    if (!interviewType) return 'bg-gray-100 text-gray-800';
    return TYPE_STYLES[interviewType] || 'bg-gray-100 text-gray-800';
  };

  const getTypeLabel = (interviewType?: string) => {
    if (!interviewType) return 'N/A';
    return TYPE_LABELS[interviewType] || interviewType;
  };

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Interview Requests</h1>
        <p className="mt-1 text-sm text-gray-600">
          All detected interview requests from your processed emails. Click a row to see the process checklist.
        </p>
      </div>

      {/* Summary Card */}
      <div className="bg-white shadow rounded-lg p-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-gray-500">Total Interview Requests</p>
            <p className="mt-1 text-3xl font-bold text-green-600">{countData?.count || 0}</p>
          </div>
          <div className="p-3 bg-green-100 rounded-full">
            <svg className="h-8 w-8 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
        </div>
      </div>

      {/* Interview Requests List */}
      <div className="bg-white shadow rounded-lg overflow-hidden">
        <div className="px-4 py-5 sm:p-6">
          <h2 className="text-lg font-medium text-gray-900 mb-4">
            Recent Interview Requests
          </h2>

          {interviews && interviews.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-8">
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Student
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Type
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Company
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Position
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Subject
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Received
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Confidence
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {interviews.map((interview: InterviewRequest) => {
                    const isExpanded = expandedInterviewId === interview.id;
                    return (
                      <Fragment key={interview.id}>
                        <tr
                          className={`cursor-pointer transition-colors ${
                            isExpanded ? 'bg-blue-50' : 'hover:bg-gray-50'
                          }`}
                          onClick={() => toggleExpand(interview.id)}
                        >
                          <td className="px-3 py-4 whitespace-nowrap">
                            <svg
                              className={`h-5 w-5 text-gray-400 transition-transform ${
                                isExpanded ? 'rotate-180' : ''
                              }`}
                              fill="none"
                              viewBox="0 0 24 24"
                              stroke="currentColor"
                            >
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                            </svg>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                            {interview.student_name || 'Unknown'}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <span className={`px-2 py-1 text-xs font-medium rounded ${getTypeStyle(interview.interview_type)}`}>
                              {getTypeLabel(interview.interview_type)}
                            </span>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                            {interview.company_name || '-'}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                            {interview.position || '-'}
                          </td>
                          <td className="px-6 py-4 text-sm text-gray-900 max-w-xs truncate">
                            {interview.subject}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                            {formatDateCST(interview.received_date)}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <span className={`px-2 py-1 text-xs font-medium rounded ${
                              interview.confidence >= 0.90
                                ? 'bg-green-100 text-green-800'
                                : interview.confidence >= 0.80
                                ? 'bg-yellow-100 text-yellow-800'
                                : 'bg-orange-100 text-orange-800'
                            }`}>
                              {(interview.confidence * 100).toFixed(0)}%
                            </span>
                          </td>
                        </tr>
                        {isExpanded && (
                          <tr>
                            <td colSpan={8} className="p-0">
                              <div onClick={(e) => e.stopPropagation()}>
                                {interview.interview_event_id ? (
                                  <InterviewChecklist interviewEventId={interview.interview_event_id} />
                                ) : (
                                  <div className="border-t border-gray-200 bg-gray-50 px-6 py-4 text-sm text-gray-500">
                                    No checklist available. This interview has not been sub-classified yet.
                                  </div>
                                )}
                              </div>
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="text-center py-12">
              <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
              </svg>
              <h3 className="mt-2 text-sm font-medium text-gray-900">No interview requests</h3>
              <p className="mt-1 text-sm text-gray-500">
                No interview requests have been detected yet.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default InterviewsPage;
