"""Configurations, secrets and URL paths."""

from decouple import config

TOKEN = config("API_KEY", None)
EMAIL = config("EMAIL", None)
JIRA_USERNAME = config("JIRA_USERNAME", None)

BASE_URL = config("BASE_URL", default="https://your-domain.atlassian.net/")
GET_ISSUE = "/rest/agile/1.0/issue/{issueIdOrKey}"
GET_ISSUE_WORKLOG = "/rest/api/2/issue/{issueIdOrKey}/worklog"
ADD_WORKLOG = "/rest/api/2/issue/{issueIdOrKey}/worklog"
GET_WORKLOG = "/rest/api/2/issue/{issueIdOrKey}/worklog/{id}"
UPDATE_WORKLOG = "/rest/api/2/issue/{issueIdOrKey}/worklog/{id}"
DELETE_WORKLOG = "/rest/api/2/issue/{issueIdOrKey}/worklog/{id}"
SEARCH_ISSUES = "/rest/api/3/search/jql"

WORK_HOURS = {
    "Monday": config("WORK_HOURS_MONDAY", default=0, cast=float),
    "Tuesday": config("WORK_HOURS_TUESDAY", default=0, cast=float),
    "Wednesday": config("WORK_HOURS_WEDNESDAY", default=0, cast=float),
    "Thursday": config("WORK_HOURS_THURSDAY", default=0, cast=float),
    "Friday": config("WORK_HOURS_FRIDAY", default=0, cast=float),
}
