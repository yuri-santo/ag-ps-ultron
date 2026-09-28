$ErrorActionPreference = "Stop"
$outlook = New-Object -ComObject Outlook.Application
$ns = $outlook.GetNamespace("MAPI")
$day = if ($args.Count -gt 0) { [datetime]$args[0] } else { [datetime]::Today }
$window = if ($args.Count -gt 1) { [int]$args[1] } else { 1 }
$startDt = $day.Date
$endDt = $startDt.AddDays($window)

$rows = @()
foreach ($acct in $ns.Accounts) {
    $email = $acct.SmtpAddress
    $store = $acct.DeliveryStore
    try {
        $cal = $store.GetRootFolder().Folders.Item("Calendário")
    } catch {
        try { $cal = $store.GetRootFolder().Folders.Item("Calendar") } catch { continue }
    }
    $items = $cal.Items
    $items.Sort("[Start]")
    $items.IncludeRecurrences = $true
    foreach ($it in $items) {
        if ($it.Start -ge $startDt -and $it.Start -lt $endDt) {
            $subject = ""
            try { $subject = [string]$it.Subject } catch {}
            $loc = ""
            try { $loc = [string]$it.Location } catch {}
            $rows += [PSCustomObject]@{
                start = $it.Start.ToString("o")
                end = $it.End.ToString("o")
                subject = $subject
                location = $loc
                account = $email
                allday = $it.AllDayEvent
            }
        }
    }
}
$rows | ConvertTo-Json -Depth 3