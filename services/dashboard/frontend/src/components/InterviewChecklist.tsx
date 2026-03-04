import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../api/client';
import type { ChecklistMainStep, ChecklistSubStep } from '../types';

interface InterviewChecklistProps {
  interviewEventId: number;
}

const InterviewChecklist = ({ interviewEventId }: InterviewChecklistProps) => {
  const queryClient = useQueryClient();

  const { data: checklist, isLoading, error } = useQuery({
    queryKey: ['checklist', interviewEventId],
    queryFn: () => apiClient.getChecklist(interviewEventId),
  });

  const toggleMutation = useMutation({
    mutationFn: (params: { stepKey: string; isCompleted: boolean }) =>
      apiClient.toggleChecklistStep(interviewEventId, params.stepKey, params.isCompleted),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['checklist', interviewEventId] });
    },
  });

  const handleToggle = (stepKey: string, currentState: boolean) => {
    toggleMutation.mutate({ stepKey, isCompleted: !currentState });
  };

  if (isLoading) {
    return (
      <div className="flex justify-center py-4">
        <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  if (error || !checklist) {
    return (
      <div className="py-4 text-center text-sm text-gray-500">
        No checklist available for this interview type.
      </div>
    );
  }

  return (
    <div className="border-t border-gray-200 bg-gray-50 px-6 py-4 space-y-4">
      {/* Header with progress */}
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-semibold text-gray-900">
          Process Checklist &mdash; {checklist.sub_type_label}
        </h4>
        <div className="flex items-center space-x-2">
          <span className="text-xs text-gray-500">
            {checklist.completed_steps}/{checklist.total_steps} steps
          </span>
          <div className="w-24 h-2 bg-gray-200 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${
                checklist.progress_percent === 100
                  ? 'bg-green-500'
                  : checklist.progress_percent > 0
                  ? 'bg-blue-500'
                  : 'bg-gray-300'
              }`}
              style={{ width: `${checklist.progress_percent}%` }}
            />
          </div>
          <span className={`text-xs font-medium ${
            checklist.progress_percent === 100 ? 'text-green-600' : 'text-gray-600'
          }`}>
            {checklist.progress_percent}%
          </span>
        </div>
      </div>

      {/* Steps */}
      <div className="space-y-3">
        {checklist.steps.map((step: ChecklistMainStep, stepIndex: number) => (
          <div key={step.key} className="bg-white border border-gray-200 rounded-lg p-3">
            {/* Main step */}
            <label className="flex items-start space-x-3 cursor-pointer">
              <input
                type="checkbox"
                checked={step.is_completed}
                onChange={() => handleToggle(step.key, step.is_completed)}
                className="mt-0.5 h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
              />
              <span className={`text-sm font-medium ${
                step.is_completed ? 'text-gray-400 line-through' : 'text-gray-900'
              }`}>
                {stepIndex + 1}. {step.label}
              </span>
            </label>

            {/* Sub-steps */}
            {step.sub_steps.length > 0 && (
              <div className="ml-7 mt-2 space-y-2">
                {step.sub_steps.map((sub: ChecklistSubStep) => (
                  <label key={sub.key} className="flex items-start space-x-3 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={sub.is_completed}
                      onChange={() => handleToggle(sub.key, sub.is_completed)}
                      className="mt-0.5 h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                    />
                    <div className="flex-1">
                      <span className={`text-sm ${
                        sub.is_completed ? 'text-gray-400 line-through' : 'text-gray-700'
                      }`}>
                        {sub.label}
                      </span>
                      {sub.completed_by && (
                        <span className="ml-2 text-xs text-gray-400">
                          by {sub.completed_by}
                        </span>
                      )}
                    </div>
                  </label>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

export default InterviewChecklist;
