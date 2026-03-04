# PowerShell script to set up email processing task in Windows Task Scheduler
#
# This creates a scheduled task that runs process_inbox_auto.py every 10 minutes

$TaskName = "ColaberryEmailProcessing"
$ScriptPath = "C:\Users\ali_m\OneDrive\Business\Colaberry Novedea\AI Projects\ClaudeTest\execution\process_inbox_auto.py"
$PythonPath = "python"  # Assumes python is in PATH
$WorkingDir = "C:\Users\ali_m\OneDrive\Business\Colaberry Novedea\AI Projects\ClaudeTest"

# Create the action
$Action = New-ScheduledTaskAction -Execute $PythonPath `
    -Argument $ScriptPath `
    -WorkingDirectory $WorkingDir

# Create trigger (every 10 minutes)
$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2) -RepetitionInterval (New-TimeSpan -Minutes 10)

# Task settings
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable

# Create the task
try {
    # Check if task already exists
    $ExistingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue

    if ($ExistingTask) {
        Write-Host "Task '$TaskName' already exists. Unregistering..." -ForegroundColor Yellow
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    }

    # Register new task
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $Action `
        -Trigger $Trigger `
        -Settings $Settings `
        -Description "Automated email processing for Colaberry interview inbox (runs every 10 minutes)" `
        -User $env:USERNAME

    Write-Host ""
    Write-Host "SUCCESS: Task '$TaskName' created!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Task Details:" -ForegroundColor Cyan
    Write-Host "  Name: $TaskName" -ForegroundColor White
    Write-Host "  Script: $ScriptPath" -ForegroundColor White
    Write-Host "  Schedule: Every 10 minutes" -ForegroundColor White
    Write-Host "  Next Run: $($(Get-Date).AddMinutes(2).ToString('yyyy-MM-dd HH:mm'))" -ForegroundColor White
    Write-Host ""
    Write-Host "To manage this task:" -ForegroundColor Cyan
    Write-Host "  View task:    Get-ScheduledTask -TaskName '$TaskName'" -ForegroundColor White
    Write-Host "  Run now:      Start-ScheduledTask -TaskName '$TaskName'" -ForegroundColor White
    Write-Host "  Disable:      Disable-ScheduledTask -TaskName '$TaskName'" -ForegroundColor White
    Write-Host "  Remove:       Unregister-ScheduledTask -TaskName '$TaskName'" -ForegroundColor White
    Write-Host ""

    # Show the task
    Get-ScheduledTask -TaskName $TaskName | Format-List

} catch {
    Write-Host "ERROR: Failed to create scheduled task" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
