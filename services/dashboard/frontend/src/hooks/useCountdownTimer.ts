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
    const nextRun = new Date(lastRun.getTime() + intervalMs);

    const updateCountdown = () => {
      const now = new Date();
      const remaining = nextRun.getTime() - now.getTime();

      if (remaining <= 0) {
        // Countdown reached zero - trigger refresh
        queryClient.invalidateQueries({ queryKey: ['summaryStats'] });
        queryClient.invalidateQueries({ queryKey: ['processingRuns'] });
        setTimeRemaining(null);
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
    intervalMinutes: scheduleConfig?.interval_minutes,
  };
};
