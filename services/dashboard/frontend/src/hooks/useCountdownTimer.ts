import { useState, useEffect } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../api/client';

const formatDuration = (ms: number): string => {
  const totalSeconds = Math.floor(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, '0')}`;
};

export const useCountdownTimer = () => {
  const queryClient = useQueryClient();
  const [timeRemaining, setTimeRemaining] = useState<number | null>(null);

  const { data: stats } = useQuery({
    queryKey: ['summaryStats'],
    queryFn: () => apiClient.getSummaryStats(),
    refetchInterval: 60000, // Refresh stats every minute
  });

  const { data: scheduleConfig } = useQuery({
    queryKey: ['scheduleConfig'],
    queryFn: () => apiClient.getScheduleConfig(),
  });

  useEffect(() => {
    if (!stats?.last_run_timestamp || !scheduleConfig?.interval_minutes) {
      setTimeRemaining(null);
      return;
    }

    // Parse the timestamp - backend sends UTC timestamps, may or may not have Z suffix
    const timestamp = stats.last_run_timestamp;
    const utcString = timestamp.endsWith('Z') || timestamp.includes('+') ? timestamp : timestamp + 'Z';
    const lastRun = new Date(utcString);
    const intervalMs = scheduleConfig.interval_minutes * 60 * 1000;

    // Calculate the next future run time, accounting for overdue schedules.
    // If the last run was more than one interval ago, project forward by the
    // number of full intervals elapsed so the countdown always shows a future time.
    const computeNextRun = (): Date => {
      const now = new Date();
      const elapsed = now.getTime() - lastRun.getTime();
      if (elapsed < intervalMs) {
        // Still within the first interval — simple next run
        return new Date(lastRun.getTime() + intervalMs);
      }
      // Overdue: find the next interval boundary ahead of now
      const intervalsPassed = Math.floor(elapsed / intervalMs) + 1;
      return new Date(lastRun.getTime() + intervalsPassed * intervalMs);
    };

    const updateCountdown = () => {
      const now = new Date();
      const nextRun = computeNextRun();
      const remaining = nextRun.getTime() - now.getTime();

      if (remaining <= 0) {
        // Still overdue after recompute — trigger a refresh and wait
        queryClient.invalidateQueries({ queryKey: ['summaryStats'] });
        queryClient.invalidateQueries({ queryKey: ['processingRuns'] });
        setTimeRemaining(intervalMs); // show full interval while waiting for refresh
      } else {
        setTimeRemaining(remaining);
      }
    };

    updateCountdown();
    const interval = setInterval(updateCountdown, 1000);
    return () => clearInterval(interval);
  }, [stats?.last_run_timestamp, scheduleConfig?.interval_minutes, queryClient]);

  return {
    timeRemaining,
    formatted: timeRemaining ? formatDuration(timeRemaining) : null,
    isRunning: timeRemaining !== null && timeRemaining > 0,
    isScheduled: !!scheduleConfig?.interval_minutes,
    intervalMinutes: scheduleConfig?.interval_minutes,
  };
};
