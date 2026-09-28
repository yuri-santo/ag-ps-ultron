$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$teamsProcesses = Get-Process -Name 'ms-teams','Teams' -ErrorAction SilentlyContinue
$clicked = $false
foreach ($teamsProcess in $teamsProcesses) {
    if ($teamsProcess.MainWindowHandle -eq 0) { continue }
    $window = [System.Windows.Automation.AutomationElement]::FromHandle($teamsProcess.MainWindowHandle)
    $buttonCondition = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty, [System.Windows.Automation.ControlType]::Button)
    $buttons = $window.FindAll([System.Windows.Automation.TreeScope]::Descendants, $buttonCondition)
    foreach ($button in $buttons) {
        $name = $button.Current.Name
        $automationId = $button.Current.AutomationId
        if ($automationId -match 'hangup|call-hangup' -or $name -match '^(Sair|Leave)( \(|$)') {
            if (-not $button.Current.IsEnabled -or $button.Current.IsOffscreen) { continue }
            $pattern = $button.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern)
            $pattern.Invoke()
            $clicked = $true
            break
        }
    }
    if ($clicked) { break }
}
@{ ok = $clicked; status = $(if ($clicked) {'leave_requested'} else {'no_active_meeting_control'}) } | ConvertTo-Json -Compress
