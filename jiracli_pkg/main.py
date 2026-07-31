"""Run Jira CLI for logging work time."""

import csv
import json
import re
from calendar import monthrange
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, date
from pathlib import Path
from typing import Tuple

import requests
import typer
from rich.console import Console
from rich.table import Table

from .utils import convert_to_hours, WORKING_DAYS
from .config import (
    ADD_WORKLOG,
    BASE_URL,
    EMAIL,
    DELETE_WORKLOG,
    GET_ISSUE,
    GET_ISSUE_WORKLOG,
    JIRA_USERNAME,
    SEARCH_ISSUES,
    TOKEN,
    UPDATE_WORKLOG,
    WORK_HOURS,
)

app = typer.Typer()
console = Console()

headers = {
    "Accept": "application/json",
    "Content-Type": "application/json"
}

WEEK_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
TIMEOUT = 15
ISSUE_KEY_PATTERN = re.compile(r'^[A-Z][A-Z0-9_]+-\d+$')


@app.command("get")
def get_issue(issue: str):
    """
    Get issue stats.
    Run this command with argument that represents Issue Key/task (e.g. jiracli get-issue KAN-3)
    """
    issue = _validate_issue_key(issue)
    raw_path = BASE_URL + GET_ISSUE
    valid_url = raw_path.replace("{issueIdOrKey}", issue)
    response = requests.get(valid_url, auth=(EMAIL, TOKEN), timeout=TIMEOUT)
    if response.status_code == 200:
        json_data = response.json()
        fields = json_data["fields"]
        assignee = fields.get("assignee").get("displayName") if fields.get("assignee") else "Unassigned"
        desc = fields.get("description")
        email = fields.get("assignee").get("emailAddress") if fields.get("assignee") else None
        status = fields.get("status").get("description")
        category = fields.get("status").get("statusCategory").get("name")
        reporter = fields.get("reporter").get("displayName")
        console.print("[cyan]Request successful[/cyan]", ":star:")
        console.print(f"[bright_green]Assignee: {assignee}[/bright_green]")
        console.print(f"[magenta]Description: {desc}[/magenta]")
        console.print(f"[bright_green]Email: {email}[/bright_green]")
        console.print(f"[bright_white]Reporter: {reporter}[/bright_white]")
        console.print(f"[bright_green]Status: {category} - {status}[/bright_green]")
    else:
        error_messages = _get_error_messages(response)
        for message in error_messages:
            console.print(f"[red]{message}[/red]")


@app.command()
def get_issue_worklogs(issue: str):
    """
    Get issue worklogs.
    Run this command with flag that represents Issue Key/task (e.g. jiracli get-issue-worklogs KAN-3)
    """
    issue = _validate_issue_key(issue)
    worklogs = _issue_worklogs(issue)
    if worklogs:
        console.print("[cyan]Request successful[/cyan]", ":boom:")
        console.print(f"Worklogs on issue {issue}")
        table = Table("Logger", "Date", "Time Spent", "Worklog ID")
        for log in worklogs:
            table.add_row(
                log.get('user'), log.get('date'), log.get('time_spent'), log.get('worklog_id')
            )
        console.print(table)

        # Summary of logged work grouped by user.
        totals_by_user = defaultdict(lambda: {"hours": 0.0, "entries": 0})
        for log in worklogs:
            user = log.get('user') or "Unknown"
            totals_by_user[user]["hours"] += convert_to_hours(log.get('time_spent', ''))
            totals_by_user[user]["entries"] += 1

        summary = Table(title="Summary by user")
        summary.add_column("Logger", style="cyan", no_wrap=True)
        summary.add_column("Entries", justify="right", no_wrap=True)
        summary.add_column("Total Hours", justify="right", no_wrap=True)

        grand_total = 0.0
        for user, data in sorted(
            totals_by_user.items(), key=lambda item: item[1]["hours"], reverse=True
        ):
            grand_total += data["hours"]
            hours_str = f"{data['hours']:.1f}h".replace(".0h", "h")
            summary.add_row(user, str(data["entries"]), hours_str)

        total_str = f"{grand_total:.1f}h".replace(".0h", "h")
        summary.add_row(
            "[bold]Total[/bold]",
            f"[bold]{len(worklogs)}[/bold]",
            f"[bold]{total_str}[/bold]",
        )
        console.print(summary)
    else:
        console.print("[red]No worklogs recorded on this issue yet.[/red]")


@app.command("add")
def add_worklog(
    issue: str,
    logged_time: str,
    date: str,
    comment: str | None = None,
    overtime: bool = False
):
    """
    Add issue worklogs.
    Run this command with Issue Key/task (e.g. KAN-3), time (examples, 7h, 7h30m, 7.5h, 20m),
    date (YYYY-MM-DD), comment (Optional) and overtime (Optional-allows logging up to 13h on a single day).
    Example: jiracli add-worklog KAN-3 7.5h 2023-12-12 --comment "Done some work here." --overtime
    """
    issue = _validate_issue_key(issue)
    _submit_worklog(issue, logged_time, date, comment, overtime)


@app.command()
def log_from_csv(csv_file: str):
    """
    Log time from the csv file.
    Run this command to log time for multiple days and issues using CSV file.
    CSV file has five columns: Working Day, Issue, Hours, Date and Overtime.

    example:
        Working Day, Issue, Time (Hours), Date, Overtime
        Monday,KAN-3,7.5h,2024-09-23,0
        Tuesday,KAN-3,7.25h,2024-09-24,0
        Wednesday,KAN-3,7.5h,2024-09-25,0
        Thursday,KAN-3,7h,2024-09-26,0
        Friday,KAN-3,7.5h,2024-09-27,0
    """
    try:
        _try_log_time_from_csv_file(csv_file)
        console.print("[green]Logging successful[/green]", ":star:")
    except FileNotFoundError as _exc:
        console.print("[red]File not found or not in the right format.[/red]")
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
    except typer.Abort:
        console.print("[red]Operation aborted.[/red]")


@app.command("update")
def update_worklog(
    issue: str,
    worklog_id: str,
    logged_time: str,
    date: str,
    comment: str | None = None
):
    """
    Update worklog.
    Run this command with Issue Key/task, Worklog ID, time, date (YYYY-MM-DD) and comment (Optional)
    """
    issue = _validate_issue_key(issue)
    seconds, _ = _validate_time(logged_time)
    payload = _build_payload(date, seconds, comment)

    raw_path = BASE_URL + UPDATE_WORKLOG
    valid_url = raw_path.replace("{issueIdOrKey}", issue).replace("{id}", worklog_id)
    response = requests.put(
        valid_url,
        data=json.dumps(payload),
        auth=(EMAIL, TOKEN),
        headers=headers,
        timeout=TIMEOUT
    )
    if response.status_code == 200:
        console.print(f'[bright_green]Comment: {response.json().get("comment")}[/bright_green]')
        console.print(f"[bright_green]Added time: {response.json().get('timeSpent')}[/bright_green]")
    else:
        error_messages = _get_error_messages(response)
        for message in error_messages:
            console.print(f"[red]{message}[/red]")


@app.command("delete")
def delete_worklog(issue: str, worklog_id: str):
    """
    Delete worklog.
    Run this command with Issue Key/task and Worklog ID.
    """
    issue = _validate_issue_key(issue)
    raw_path = BASE_URL + DELETE_WORKLOG
    valid_url = raw_path.replace("{issueIdOrKey}", issue).replace("{id}", worklog_id)
    response = requests.delete(
        valid_url,
        auth=(EMAIL, TOKEN),
        headers=headers,
        timeout=TIMEOUT
    )
    if response.status_code == 204:
        console.print("[green]Worklog deleted successfully.[/green]", ":boom:")
    else:
        error_messages = _get_error_messages(response)
        for message in error_messages:
            console.print(f"[red]{message}[/red]")


@app.command("my-issues")
def my_issues(max_results: int = 50):
    """
    List issues currently assigned to you.
    Uses JQL: assignee=currentUser() AND status!=Done.
    Example: jiracli my-issues --max-results 20
    """
    jql = 'assignee=currentUser() AND status!=Done ORDER BY updated DESC'
    url = BASE_URL + SEARCH_ISSUES
    response = requests.get(
        url,
        params={"jql": jql, "fields": "key,summary,status,priority", "maxResults": max_results},
        auth=(EMAIL, TOKEN),
        timeout=TIMEOUT
    )
    if response.status_code != 200:
        error_messages = _get_error_messages(response)
        for message in error_messages:
            console.print(f"[red]{message}[/red]")
        return

    issues = response.json().get("issues", [])
    if not issues:
        console.print("[yellow]No issues found.[/yellow]")
        return

    def _issue_sort_key(jira_issue: dict) -> tuple[str, int]:
        ticket_key = jira_issue["key"]
        prefix, num = ticket_key.rsplit("-", 1)
        return prefix, -int(num)

    issues.sort(key=_issue_sort_key)
    console.print(f"Found {len(issues)} issues assigned to you.")

    def _my_hours_for(issue_key: str) -> float:
        return sum(
            convert_to_hours(log["time_spent"])
            for log in _issue_worklogs(issue_key)
            if log["email"] == EMAIL
        )

    keys = [issue["key"] for issue in issues]
    with ThreadPoolExecutor(max_workers=min(16, len(keys))) as pool:
        hours_by_key = dict(zip(keys, pool.map(_my_hours_for, keys)))

    table = Table("Key", "Summary", "Status", "Priority", "My Hours", "Link")
    for issue in issues:
        fields = issue["fields"]
        key = issue["key"]
        summary = fields.get("summary", "")
        if len(summary) > 60:
            summary = summary[:57] + "..."
        status = fields.get("status", {}).get("name", "Unknown")
        status_lower = status.lower()
        if "to do" in status_lower:
            status = f"[red]{status}[/red]"
        elif "in progress" in status_lower:
            status = f"[yellow]{status}[/yellow]"
        priority = fields.get("priority", {}).get("name", "None") if fields.get("priority") else "None"
        my_hours = hours_by_key[key]
        my_hours_str = f"{my_hours:.1f}h".replace(".0h", "h")
        if my_hours == 0:
            my_hours_str = f"[dim]{my_hours_str}[/dim]"
        link = f"{BASE_URL}browse/{key}"
        table.add_row(key, summary, status, priority, my_hours_str, link)

    console.print(table)


@app.command("search")
def search_issues(text: str, max_results: int = 10):
    """
    Search Jira issues by text.
    Searches across summary, description, and comments.
    Example: jiracli search "login bug" --max-results 5
    """
    jql = f'text ~ "{text}" ORDER BY updated DESC'
    url = BASE_URL + SEARCH_ISSUES
    response = requests.get(
        url,
        params={"jql": jql, "fields": "key,summary,status,assignee", "maxResults": max_results},
        auth=(EMAIL, TOKEN),
        timeout=TIMEOUT
    )
    if response.status_code != 200:
        error_messages = _get_error_messages(response)
        for message in error_messages:
            console.print(f"[red]{message}[/red]")
        return

    issues = response.json().get("issues", [])
    if not issues:
        console.print("[yellow]No issues found.[/yellow]")
        return

    table = Table("Key", "Summary", "Status", "Assignee", "Link")
    for issue in issues:
        fields = issue["fields"]
        key = issue["key"]
        summary = fields.get("summary", "")
        if len(summary) > 60:
            summary = summary[:57] + "..."
        status = fields.get("status", {}).get("name", "Unknown")
        assignee = fields.get("assignee", {}).get("displayName", "Unassigned") if fields.get("assignee") else "Unassigned"
        link = f"{BASE_URL}browse/{key}"
        table.add_row(key, summary, status, assignee, link)

    console.print(table)


@app.command("my-worklogs")
def my_worklogs(month: int | None = None, year: int | None = None):
    """
    Display all your worklogs for a given month in a table grouped by day.
    Defaults to the current month. Example: jiracli my-worklogs --month 3 --year 2026
    """
    user = JIRA_USERNAME
    if not user:
        console.print("[red]JIRA_USERNAME environment variable is not set.[/red]")
        raise typer.Abort()

    today = date.today()
    target_year = year or today.year
    target_month = month or today.month

    first_day = date(target_year, target_month, 1)
    last_day_num = monthrange(target_year, target_month)[1]
    last_day = date(target_year, target_month, last_day_num)

    jql = (
        f'worklogAuthor = "{user}" '
        f'AND worklogDate >= "{first_day}" '
        f'AND worklogDate <= "{last_day}"'
    )
    url = BASE_URL + SEARCH_ISSUES
    response = requests.get(
        url,
        params={"jql": jql, "fields": "key,summary", "maxResults": 100, "nextPageToken": ""},
        auth=(EMAIL, TOKEN),
        timeout=TIMEOUT,
    )
    if response.status_code != 200:
        for msg in _get_error_messages(response):
            console.print(f"[red]{msg}[/red]")
        return

    issues = response.json().get("issues", [])
    if not issues:
        console.print("[yellow]No worklogs found for this month.[/yellow]")
        return

    summaries = {}
    for issue_data in issues:
        key = issue_data["key"]
        summary = issue_data["fields"].get("summary", "")
        if len(summary) > 45:
            summary = summary[:42] + "..."
        summaries[key] = summary

    keys = [issue_data["key"] for issue_data in issues]
    with ThreadPoolExecutor(max_workers=min(16, len(keys))) as pool:
        worklogs_by_key = dict(zip(keys, pool.map(_issue_worklogs, keys)))

    # date -> list of {issue, summary, time_spent}
    day_entries = defaultdict(list)
    for key in keys:
        worklogs = worklogs_by_key[key]
        for log in worklogs:
            if log["email"] != EMAIL:
                continue
            log_date = log["date"]
            log_date_obj = datetime.strptime(log_date, "%Y-%m-%d").date()
            if log_date_obj.month != target_month or log_date_obj.year != target_year:
                continue
            day_entries[log_date].append({
                "issue": key,
                "summary": summaries[key],
                "time_spent": log["time_spent"],
                "link": f"{BASE_URL}browse/{key}",
            })

    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    default_expected = 8.0

    table = Table(title=f"Worklogs for {first_day.strftime('%B %Y')}")
    table.add_column("Date", style="cyan", no_wrap=True)
    table.add_column("Day", style="cyan", no_wrap=True)
    table.add_column("Issue", style="bright_green", no_wrap=True)
    table.add_column("Summary")
    table.add_column("Time", no_wrap=True)
    table.add_column("Daily Total", no_wrap=True)
    table.add_column("Expected", no_wrap=True)
    table.add_column("Link", style="dim")

    total_logged = 0.0
    total_expected = 0.0

    for day_offset in range(last_day_num):
        current_date = date(target_year, target_month, 1 + day_offset)
        date_str = current_date.strftime("%Y-%m-%d")
        weekday = current_date.weekday()
        day_name = day_names[weekday]
        is_weekend = weekday >= 5

        entries = day_entries.get(date_str, [])

        day_label = WEEK_DAYS[weekday] if weekday < 5 else day_name
        expected_hours = WORK_HOURS.get(day_label, 0) if weekday < 5 else 0
        if expected_hours == 0 and weekday < 5:
            expected_hours = default_expected

        day_total = sum(convert_to_hours(e["time_spent"]) for e in entries)
        total_logged += day_total
        total_expected += expected_hours

        if is_weekend and not entries:
            table.add_row(
                f"[dim]{date_str}[/dim]", f"[dim]{day_name}[/dim]",
                "", "", "", "", "[dim]0h[/dim]", "",
            )
        elif not entries:
            daily_str = "[red]0h[/red]"
            expected_str = f"{expected_hours:.1f}h".replace(".0h", "h") if expected_hours else ""
            if expected_hours > 0:
                expected_str = f"[red]{expected_str}[/red]"
            table.add_row(date_str, day_name, "", "", "", daily_str, expected_str, "")
        else:
            for i, entry in enumerate(entries):
                if i == len(entries) - 1:
                    daily_str = f"{day_total:.1f}h".replace(".0h", "h")
                    expected_str = f"{expected_hours:.1f}h".replace(".0h", "h") if expected_hours else "0h"
                    if is_weekend:
                        daily_str = f"[dim]{daily_str}[/dim]"
                        expected_str = f"[dim]{expected_str}[/dim]"
                    elif day_total < expected_hours:
                        daily_str = f"[yellow]{daily_str}[/yellow]"
                        expected_str = f"[yellow]{expected_str}[/yellow]"
                    elif day_total >= expected_hours and expected_hours > 0:
                        daily_str = f"[green]{daily_str}[/green]"
                        expected_str = f"[green]{expected_str}[/green]"
                else:
                    daily_str = ""
                    expected_str = ""

                date_col = date_str if i == 0 else ""
                day_col = day_name if i == 0 else ""
                if is_weekend and i == 0:
                    date_col = f"[dim]{date_str}[/dim]"
                    day_col = f"[dim]{day_name}[/dim]"

                table.add_row(
                    date_col,
                    day_col,
                    f"[dim]{entry['issue']}[/dim]" if is_weekend else entry["issue"],
                    f"[dim]{entry['summary']}[/dim]" if is_weekend else entry["summary"],
                    f"[dim]{entry['time_spent']}[/dim]" if is_weekend else entry["time_spent"],
                    daily_str,
                    expected_str,
                    f"[dim]{entry['link']}[/dim]" if is_weekend else entry["link"],
                )

        table.add_section()

    total_logged_str = f"{total_logged:.1f}h".replace(".0h", "h")
    total_expected_str = f"{total_expected:.1f}h".replace(".0h", "h")
    color = "green" if total_logged >= total_expected else "yellow"
    table.add_row(
        "", "", "", "", "",
        f"[bold {color}]{total_logged_str}[/bold {color}]",
        f"[bold]{total_expected_str}[/bold]",
        "",
    )

    console.print(table)


def _validate_issue_key(issue: str) -> str:
    """Validate and normalize a Jira issue key. Returns the uppercased key."""
    normalized = issue.strip().upper()
    if not ISSUE_KEY_PATTERN.match(normalized):
        console.print(f"[red]Invalid issue key '{issue}'. Expected format: PROJECT-123 (e.g. KAN-3).[/red]")
        raise typer.Abort()
    return normalized


def _get_error_messages(response: requests.Response) -> list[str]:
    try:
        messages = response.json().get("errorMessages", [])
        if messages:
            return messages
        return [f"Request failed with status {response.status_code}."]
    except requests.exceptions.JSONDecodeError:
        return [f"Server error (status {response.status_code}): {response.text[:200]}"]


def _submit_worklog(
    issue: str,
    logged_time: str,
    date: str,
    comment: str | None,
    overtime: bool
) -> bool:
    seconds, hours = _validate_time(logged_time)
    payload = _build_payload(date, seconds, comment)

    total_hours_on_date = _get_total_hours_on_date(date)
    if total_hours_on_date is None:
        console.print("[red]You haven't provided Jira account username as an environment variable.[/red]")
        raise typer.Abort()
    new_total = total_hours_on_date + hours
    if overtime and new_total > 13:
        console.print("[red]You've exceeded the maximum of 13 working hours a day for overtime.[/red]")
        raise typer.Abort()
    if not overtime and new_total > 8:
        console.print("[red]You've exceeded the maximum of 8 working hours a day."
                      " If you want to log anyway, run the same command with --overtime.[/red]")
        raise typer.Abort()

    date_object = datetime.strptime(date, "%Y-%m-%d")
    day_of_week = date_object.weekday()
    day = WEEK_DAYS[day_of_week]
    work_hours = WORK_HOURS.get(day)

    if work_hours:
        if (hours > work_hours and not overtime) or (total_hours_on_date >= work_hours and not overtime):
            console.print("[red]Based on the template of your working hours you've exceeded your daily norm."
                          " If you want to log anyway, run the same command with additional argument --overtime.[/red]")
            raise typer.Abort()

    raw_path = BASE_URL + ADD_WORKLOG
    valid_url = raw_path.replace("{issueIdOrKey}", issue)
    response = requests.post(
        valid_url,
        data=json.dumps(payload),
        auth=(EMAIL, TOKEN),
        headers=headers,
        timeout=TIMEOUT
    )
    if response.status_code == 201:
        console.print(f"[green]Added time: {response.json().get('timeSpent')}[/green]")
        return True
    else:
        error_messages = _get_error_messages(response)
        for message in error_messages:
            console.print(f"[red]{message}[/red]")
        return False


def _build_payload(date: str, seconds: int, comment: str | None) -> dict:
    """Build the payload for Jira worklog submission."""
    if _is_iso_date_format(date):
        return {
            "comment": f"{comment}",
            "started": f"{date}T00:00:00.000+0000",
            "timeSpentSeconds": int(seconds)
        }
    else:
        console.print("[bright_red]Invalid date format. Please use 'YYYY-MM-DD' format.[/bright_red]")
        raise typer.Abort()


def _is_valid_time_format(logged_time: str) -> bool:
    """
    Check if the logged_time string is in a valid format.
    Valid formats now include decimal hours like '7.5h', or hours and minutes combinations like '15m', '7.5h20m' or '2h30m'.
    """
    return bool(re.fullmatch(r'(\d+(\.\d+)?h)?(\d+m)?', logged_time) and logged_time)


def _is_iso_date_format(value: str) -> bool:
    """Determine if the string matches the ISO format."""
    pattern = r"^\d{4}-([0]\d|1[0-2])-([0-2]\d|3[01])$"
    if value is None:
        return False
    return re.match(pattern, value) is not None


def _time_to_seconds(logged_time: str) -> Tuple[int, float]:
    """Return amount of seconds and decimal hours to be added to worklog."""

    hours = re.search(r'(\d+(\.\d+)?)h', logged_time)
    minutes = re.search(r'(\d+)m', logged_time)

    if hours:
        # split decimal hours into hours and minutes
        hour_parts = hours.group(1).split('.')
        hours = int(hour_parts[0])
        if len(hour_parts) > 1:
            # convert decimal part to minutes (0.5 hours = 30 minutes)
            minutes_decimal = float("0." + hour_parts[1]) * 60
            minutes = int(minutes.group(1)) if minutes else 0
            minutes += int(round(minutes_decimal))
        else:
            minutes = int(minutes.group(1)) if minutes else 0
    else:
        hours, minutes = 0, int(minutes.group(1)) if minutes else 0

    total_seconds = (hours * 3600) + (minutes * 60)
    # convert total seconds to decimal hours
    total_hours = total_seconds / 3600
    return total_seconds, total_hours


def _validate_time(logged_time: str) -> Tuple[int, float]:
    """Validator used in time logging functions."""

    if not _is_valid_time_format(logged_time):
        console.print(
            "[bright_red]Invalid time format. Please use 'NhNm - e.g. 7h30m' format.[/bright_red]")
        raise typer.Abort()

    seconds, hours = _time_to_seconds(logged_time)

    return seconds, hours


def _get_total_hours_on_date(date: str) -> float | None:
    """Get total hours logged by the current user across all issues on a given date."""
    user = JIRA_USERNAME
    if user is None:
        return None

    jql = f'worklogAuthor = "{user}" AND worklogDate = "{date}"'
    url = BASE_URL + SEARCH_ISSUES
    response = requests.get(
        url,
        params={"jql": jql, "fields": "key", "maxResults": 100, "nextPageToken": ""},
        auth=(EMAIL, TOKEN),
        timeout=TIMEOUT
    )
    if response.status_code != 200:
        error_messages = _get_error_messages(response)
        for message in error_messages:
            console.print(f"[red]{message}[/red]")
        return None

    issues = response.json().get("issues", [])
    total_hours = 0.0
    for issue_data in issues:
        key = issue_data["key"]
        worklogs = _issue_worklogs(key)
        total_hours += sum(
            convert_to_hours(log["time_spent"])
            for log in worklogs
            if (log["email"] == EMAIL or log["user"] == user) and log["date"] == date
        )
    return total_hours


def _issue_worklogs(issue: str) -> list[dict]:
    worklogs = []
    raw_path = BASE_URL + GET_ISSUE_WORKLOG
    valid_url = raw_path.replace("{issueIdOrKey}", issue)
    response = requests.get(
        valid_url,
        auth=(EMAIL, TOKEN),
        timeout=TIMEOUT
    )
    if response.status_code == 200:
        for logger in response.json().get("worklogs"):
            author = logger.get('author', {})
            user = author.get('displayName')
            email = author.get('emailAddress', '')
            date_info = logger.get('started')
            pure_date = date_info.split("T")[0]
            time_spent = logger.get('timeSpent')
            worklog_id = logger.get('id')

            worklogs.append({
                "user": user,
                "email": email,
                "date": pure_date,
                "time_spent": time_spent,
                "worklog_id": worklog_id
            })
    else:
        error_messages = _get_error_messages(response)
        for message in error_messages:
            console.print(f"[red]{message}[/red]")
    return worklogs


def _try_log_time_from_csv_file(file: str) -> None:
    """Log time from CSV file."""

    filename = Path(file)
    if not filename.suffix.lower() == '.csv':
        raise ValueError("File is not a CSV file.")

    status = _load_status(file)
    if status["complete"]:
        raise ValueError("CSV file already logged.")

    logged_rows = status["logged_rows"]
    failed_rows = []

    with open(file) as read_file:
        csv_reader = csv.reader(read_file, delimiter=',')
        for indx, row in enumerate(csv_reader):
            if indx == 0 and row[0] == "Working Day":
                console.print("[dim]Skipping headers...[/dim]")
                continue
            if row[0].startswith("#"):
                console.print("[dim]Skipping comments...[/dim]")
                continue
            if not any(field.strip() for field in row):
                continue

            if indx in logged_rows:
                console.print(f"[dim]Row {indx}: already logged, skipping.[/dim]")
                continue

            try:
                day_of_the_week = row[0]
                if day_of_the_week in WORKING_DAYS:
                    issue = _validate_issue_key(row[1])
                    logged_time = row[2]
                    date = row[3]
                    overtime = bool(int(row[4]))
                    success = _submit_worklog(
                        issue=issue, logged_time=logged_time, date=date,
                        comment=None, overtime=overtime,
                    )
                    if success:
                        logged_rows.add(indx)
                        _save_status(file, logged_rows, complete=False)
                    else:
                        failed_rows.append(indx)
                else:
                    raise ValueError("First column is reserved for name of the working day.")
            except typer.Abort:
                console.print(f"[yellow]Row {indx}: validation failed, skipping.[/yellow]")
                failed_rows.append(indx)
            except IndexError:
                raise ValueError("CSV file not properly formatted.")

    if failed_rows:
        _save_status(file, logged_rows, complete=False)
        raise ValueError(f"Some rows failed to log: {failed_rows}. Re-run to retry.")

    _save_status(file, logged_rows, complete=True)


def _get_status_file_path(csv_file: str) -> Path:
    """Return the path to the sidecar status file for a CSV file."""
    csv_path = Path(csv_file).resolve()
    return csv_path.parent / f".{csv_path.name}.status"


def _load_status(csv_file: str) -> dict:
    """Load the sidecar status file. Returns default status if absent."""
    status_path = _get_status_file_path(csv_file)
    if status_path.exists():
        with open(status_path, "r") as f:
            data = json.load(f)
            data["logged_rows"] = set(data.get("logged_rows", []))
            return data
    return {"logged_rows": set(), "complete": False}


def _save_status(csv_file: str, logged_rows: set, complete: bool):
    """Write the sidecar status file with row indices, completion flag, and timestamp."""
    status_path = _get_status_file_path(csv_file)
    data = {
        "logged_rows": sorted(logged_rows),
        "complete": complete,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(status_path, "w") as f:
        json.dump(data, f, indent=2)


if __name__ == "__main__":
    app()
