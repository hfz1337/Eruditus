"""Tests for platforms module."""

from platforms.base import (
    Challenge,
    ChallengeFile,
    PlatformCTX,
    RegistrationStatus,
    Retries,
    Session,
    SubmittedFlag,
    SubmittedFlagState,
    Team,
)


class TestSession:
    """Tests for Session dataclass."""

    def test_empty_session_invalid(self):
        """Test that empty session is invalid."""
        session = Session()
        assert session.validate() is False

    def test_session_with_token_valid(self):
        """Test that session with token is valid."""
        session = Session(token="abc123")
        assert session.validate() is True

    def test_session_with_cookies_valid(self):
        """Test that session with cookies is valid."""
        session = Session(cookies={"session": "xyz"})
        assert session.validate() is True

    def test_session_with_empty_cookies_invalid(self):
        """Test that session with empty cookies dict is invalid."""
        session = Session(cookies={})
        assert session.validate() is False


class TestPlatformCTX:
    """Tests for PlatformCTX dataclass."""

    def test_url_stripped_removes_trailing_slash(self):
        """Test that url_stripped removes trailing slash."""
        ctx = PlatformCTX(base_url="https://ctf.example.com/")
        assert ctx.url_stripped == "https://ctf.example.com"

    def test_url_stripped_no_change_needed(self):
        """Test url_stripped with no trailing slash."""
        ctx = PlatformCTX(base_url="https://ctf.example.com")
        assert ctx.url_stripped == "https://ctf.example.com"

    def test_from_credentials(self):
        """Test creating PlatformCTX from credentials dict."""
        creds = {
            "url": "https://ctf.example.com",
            "username": "team",
            "password": "secret",
        }
        ctx = PlatformCTX.from_credentials(creds)
        assert ctx.base_url == "https://ctf.example.com"
        assert ctx.args == creds

    def test_get_args_filters_fields(self):
        """Test get_args returns only requested fields."""
        ctx = PlatformCTX(
            base_url="https://ctf.example.com",
            args={"username": "team", "password": "secret", "email": "a@b.com"},
        )
        result = ctx.get_args("username", "password")
        assert result == {"username": "team", "password": "secret"}
        assert "email" not in result

    def test_get_args_with_kwargs(self):
        """Test get_args with additional kwargs."""
        ctx = PlatformCTX(
            base_url="https://ctf.example.com",
            args={"username": "team"},
        )
        result = ctx.get_args("username", extra="value")
        assert result == {"username": "team", "extra": "value"}

    def test_is_authorized_no_session(self):
        """Test is_authorized returns False with no session."""
        ctx = PlatformCTX(base_url="https://ctf.example.com")
        assert ctx.is_authorized() is False

    def test_is_authorized_invalid_session(self):
        """Test is_authorized returns False with invalid session."""
        ctx = PlatformCTX(
            base_url="https://ctf.example.com",
            session=Session(),
        )
        assert ctx.is_authorized() is False

    def test_is_authorized_valid_session(self):
        """Test is_authorized returns True with valid session."""
        ctx = PlatformCTX(
            base_url="https://ctf.example.com",
            session=Session(token="valid_token"),
        )
        assert ctx.is_authorized() is True


class TestTeam:
    """Tests for Team dataclass."""

    def test_team_equality_by_id(self):
        """Test team equality by ID."""
        team1 = Team(id="123", name="Team A")
        team2 = Team(id="123", name="Team B")
        assert team1 == team2

    def test_team_equality_by_name(self):
        """Test team equality by name."""
        team1 = Team(id="1", name="Team A")
        team2 = Team(id="2", name="Team A")
        assert team1 == team2

    def test_team_inequality(self):
        """Test team inequality."""
        team1 = Team(id="1", name="Team A")
        team2 = Team(id="2", name="Team B")
        assert team1 != team2

    def test_team_not_equal_to_none(self):
        """Test team is not equal to None."""
        team = Team(id="1", name="Team A")
        assert team != None  # noqa: E711


class TestChallenge:
    """Tests for Challenge dataclass."""

    def test_challenge_minimal(self):
        """Test creating challenge with minimal fields."""
        chall = Challenge(
            id="1",
            name="Test Challenge",
            category="web",
            description="A test challenge",
        )
        assert chall.id == "1"
        assert chall.name == "Test Challenge"
        assert chall.solved_by_me is False

    def test_challenge_with_files(self):
        """Test challenge with file attachments."""
        files = [
            ChallengeFile(url="https://example.com/file.zip", name="file.zip"),
            ChallengeFile(url="https://example.com/hint.txt"),
        ]
        chall = Challenge(
            id="1",
            name="Test",
            category="misc",
            description="Test",
            files=files,
        )
        assert len(chall.files) == 2
        assert chall.files[0].name == "file.zip"


class TestSubmittedFlag:
    """Tests for SubmittedFlag dataclass."""

    def test_correct_flag(self):
        """Test correct flag submission."""
        flag = SubmittedFlag(state=SubmittedFlagState.CORRECT)
        assert flag.state == SubmittedFlagState.CORRECT
        assert flag.is_first_blood is False

    def test_incorrect_flag(self):
        """Test incorrect flag submission."""
        flag = SubmittedFlag(state=SubmittedFlagState.INCORRECT)
        assert flag.state == SubmittedFlagState.INCORRECT

    def test_flag_with_retries(self):
        """Test flag submission with retries info."""
        flag = SubmittedFlag(
            state=SubmittedFlagState.INCORRECT,
            retries=Retries(left=2, out_of=5),
        )
        assert flag.retries.left == 2
        assert flag.retries.out_of == 5

    def test_first_blood_flag(self):
        """Test first blood flag submission."""
        flag = SubmittedFlag(
            state=SubmittedFlagState.CORRECT,
            is_first_blood=True,
        )
        assert flag.is_first_blood is True


class TestSubmittedFlagState:
    """Tests for SubmittedFlagState enum."""

    def test_all_states_exist(self):
        """Test that all expected states exist."""
        states = [
            SubmittedFlagState.ALREADY_SUBMITTED,
            SubmittedFlagState.INCORRECT,
            SubmittedFlagState.CORRECT,
            SubmittedFlagState.CTF_NOT_STARTED,
            SubmittedFlagState.CTF_PAUSED,
            SubmittedFlagState.CTF_ENDED,
            SubmittedFlagState.INVALID_CHALLENGE,
            SubmittedFlagState.INVALID_USER,
            SubmittedFlagState.RATE_LIMITED,
            SubmittedFlagState.UNKNOWN,
        ]
        assert len(states) == 10


class TestRegistrationStatus:
    """Tests for RegistrationStatus dataclass."""

    def test_successful_registration(self):
        """Test successful registration."""
        status = RegistrationStatus(success=True, message="Welcome!")
        assert status.success is True
        assert status.message == "Welcome!"

    def test_failed_registration(self):
        """Test failed registration."""
        status = RegistrationStatus(success=False, message="Username taken")
        assert status.success is False

    def test_registration_with_token(self):
        """Test registration with token (rCTF style)."""
        status = RegistrationStatus(
            success=True,
            token="auth_token",
            invite="https://rctf.example.com/invite/abc",
        )
        assert status.token == "auth_token"
        assert status.invite is not None
