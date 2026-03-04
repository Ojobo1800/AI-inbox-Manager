import { useCountdownTimer } from '../hooks/useCountdownTimer';

interface CountdownTimerProps {
  variant?: 'nav' | 'card';
}

const CountdownTimer = ({ variant = 'nav' }: CountdownTimerProps) => {
  const { formatted, isRunning, intervalMinutes } = useCountdownTimer();

  if (variant === 'nav') {
    return (
      <span className="text-xs text-gray-500 ml-4">
        {isRunning ? (
          <>
            Next run in: <span className="font-mono font-medium text-primary-600">{formatted}</span>
          </>
        ) : (
          <span className="text-gray-400">No scheduled runs</span>
        )}
      </span>
    );
  }

  // Card variant for dashboard
  return (
    <div className="bg-white overflow-hidden shadow rounded-lg">
      <div className="p-5 text-center">
        <div className="text-sm text-gray-500 mb-1">Next Processing Run</div>
        {isRunning ? (
          <>
            <div className="text-4xl font-bold font-mono text-primary-600">
              {formatted}
            </div>
            <div className="text-xs text-gray-400 mt-1">
              runs every {intervalMinutes} min
            </div>
          </>
        ) : (
          <div className="text-lg text-gray-400">
            No scheduled runs
          </div>
        )}
      </div>
    </div>
  );
};

export default CountdownTimer;
