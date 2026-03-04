# PowerShell script to update the email processing scheduled task interval
#
# This updates an existing scheduled task with a new repetition interval

param(
    [Parameter(Mandatory=$true)]
    [int]$IntervalMinutes
)

$TaskName = "ColaberryEmailProcessing"
$ScriptPath = "C:\Users\ali_m\OneDrive\Business\Colaberry Novedea\AI Projects\ClaudeTest\execution\process_inbox_auto.py"
$PythonPath = "python"
$WorkingDir = "C:\Users\ali_m\OneDrive\Business\Colaberry Novedea\AI Projects\ClaudeTest"

try {
    # Check if task exists
    $ExistingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue

    if (-not $ExistingTask) {
        Write-Host "ERROR: Task '$TaskName' does not exist" -ForegroundColor Red
        exit 1
    }

    Write-Host "Updating task '$TaskName' to run every $IntervalMinutes minutes..." -ForegroundColor Cyan

    # Create the action
    $Action = New-ScheduledTaskAction -Execute $PythonPath `
        -Argument $ScriptPath `
        -WorkingDirectory $WorkingDir

    # Create new trigger with updated interval
    $Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes)

    # Task settings
    $Settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -RunOnlyIfNetworkAvailable

    # Unregister existing task
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false

    # Register updated task
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $Action `
        -Trigger $Trigger `
        -Settings $Settings `
        -Description "Automated email processing for Colaberry interview inbox (runs every $IntervalMinutes minutes)" `
        -User $env:USERNAME | Out-Null

    Write-Host "SUCCESS: Task updated to run every $IntervalMinutes minutes" -ForegroundColor Green
    Write-Host "  Next Run: $($(Get-Date).AddMinutes(1).ToString('yyyy-MM-dd HH:mm'))" -ForegroundColor White

    exit 0

} catch {
    Write-Host "ERROR: Failed to update scheduled task" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
