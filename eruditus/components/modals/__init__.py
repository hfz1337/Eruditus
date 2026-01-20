"""Modal components (forms)."""

from components.modals.contact import BugReportForm, FeatureRequestForm
from components.modals.credentials import CredentialsForm
from components.modals.flag import FlagSubmissionForm

__all__ = [
    "CredentialsForm",
    "FlagSubmissionForm",
    "BugReportForm",
    "FeatureRequestForm",
]
