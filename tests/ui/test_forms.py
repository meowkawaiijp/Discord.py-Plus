import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import discord

from dispyplus.ui.forms import DispyplusForm, text_field, BaseFormField, TextInputFormField
from dispyplus.core.context import EnhancedContext # For testing the helper

# --- Mocks and Fixtures ---

@pytest.fixture
def mock_interaction():
    interaction = AsyncMock(spec=discord.Interaction)
    interaction.response = AsyncMock(spec=discord.InteractionResponse)
    interaction.followup = AsyncMock(spec=discord.Webhook)
    interaction.user = AsyncMock(spec=discord.User)
    interaction.user.id = 12345
    interaction.message = None
    interaction.response.is_done.return_value = False
    # Add a client mock for logger access if forms try to use it via ctx.bot.logger
    interaction.client = MagicMock()
    interaction.client.logger = MagicMock()
    return interaction

@pytest.fixture
def mock_context(mock_interaction):
    ctx = AsyncMock(spec=EnhancedContext)
    ctx.author = mock_interaction.user
    ctx.interaction = mock_interaction # Simulate interaction context for ask_form
    ctx.send = AsyncMock(return_value=AsyncMock(spec=discord.Message))
    ctx.bot = MagicMock()
    ctx.bot.logger = MagicMock()
    return ctx

# --- Test Forms ---

class SimpleTestForm(DispyplusForm):
    form_title = "Test Form"
    name: str = text_field(label="Your Name", required=True)
    age: int = text_field(label="Your Age", target_type=int, required=False)

    async def process_form_data(self, interaction: discord.Interaction, data: dict):
        # In real usage, this would do something with data
        # For testing, we can set the future here if not testing ask_form directly
        if not self.future.done():
            self.future.set_result(data)

class ValidationTestForm(DispyplusForm):
    form_title = "Validation Test"
    email: str = text_field(
        label="Email",
        validator=lambda v, i: ("@" in v, "Must be a valid email.")
    )
    is_member: bool = text_field(label="Is Member?", target_type=bool, required=True)

    async def process_form_data(self, interaction: discord.Interaction, data: dict):
        if not self.future.done():
            self.future.set_result(data)

# --- Tests ---

@pytest.mark.asyncio
async def test_form_init_and_build_fields():
    form = SimpleTestForm()
    assert form.title == "Test Form"
    assert len(form.children) == 2 # name and age fields

    name_field_def = form._declared_fields.get("name")
    age_field_def = form._declared_fields.get("age")

    assert isinstance(name_field_def, TextInputFormField)
    assert name_field_def.label == "Your Name"
    assert name_field_def.required is True
    assert name_field_def.component_instance is not None # Should be created in _build_fields
    assert isinstance(name_field_def.component_instance, discord.ui.TextInput)
    assert name_field_def.component_instance.label == "Your Name"

    assert isinstance(age_field_def, TextInputFormField)
    assert age_field_def.target_type is int
    assert age_field_def.required is False
    assert age_field_def.component_instance is not None
    assert isinstance(age_field_def.component_instance, discord.ui.TextInput)

@pytest.mark.asyncio
async def test_form_on_submit_success(mock_interaction):
    form = SimpleTestForm(ctx=MagicMock()) # Pass a mock ctx if form uses it internally

    # Simulate user input by setting values on the TextInput instances
    # These instances are stored in form_field_def.component_instance
    form._declared_fields["name"].component_instance.value = "John Doe"
    form._declared_fields["age"].component_instance.value = "30"

    await form.on_submit(mock_interaction)

    result = await asyncio.wait_for(form.future, timeout=1)
    assert result == {"name": "John Doe", "age": 30}
    # process_form_data should have been called, which sets the future.
    # In this test, interaction.response.send_message is not directly checked from on_submit
    # as process_form_data is user-defined. We check the future.

@pytest.mark.asyncio
async def test_form_on_submit_validation_error_required(mock_interaction):
    form = SimpleTestForm(ctx=MagicMock())
    form._declared_fields["name"].component_instance.value = "" # Name is required
    form._declared_fields["age"].component_instance.value = "30"

    # Patch handle_validation_errors to check its call
    with patch.object(form, 'handle_validation_errors', new_callable=AsyncMock) as mock_handle_errors:
        await form.on_submit(mock_interaction)
        mock_handle_errors.assert_called_once()
        validation_errors_arg = mock_handle_errors.call_args[0][1] # errors dict
        assert "name" in validation_errors_arg
        assert "is required" in validation_errors_arg["name"]

    result = await asyncio.wait_for(form.future, timeout=1) # Should be None due to validation error
    assert result is None


@pytest.mark.asyncio
async def test_form_on_submit_type_conversion_error(mock_interaction):
    form = SimpleTestForm(ctx=MagicMock())
    form._declared_fields["name"].component_instance.value = "Jane Doe"
    form._declared_fields["age"].component_instance.value = "thirty" # Invalid int

    with patch.object(form, 'handle_validation_errors', new_callable=AsyncMock) as mock_handle_errors:
        await form.on_submit(mock_interaction)
        mock_handle_errors.assert_called_once()
        errors_arg = mock_handle_errors.call_args[0][1]
        assert "age" in errors_arg
        assert "Invalid type for Your Age" in errors_arg["age"]

    result = await asyncio.wait_for(form.future, timeout=1)
    assert result is None

@pytest.mark.asyncio
async def test_form_on_submit_custom_validator_fail(mock_interaction):
    form = ValidationTestForm(ctx=MagicMock())
    form._declared_fields["email"].component_instance.value = "notanemail"
    form._declared_fields["is_member"].component_instance.value = "true" # Valid bool

    with patch.object(form, 'handle_validation_errors', new_callable=AsyncMock) as mock_handle_errors:
        await form.on_submit(mock_interaction)
        mock_handle_errors.assert_called_once()
        errors_arg = mock_handle_errors.call_args[0][1]
        assert "email" in errors_arg
        assert "Must be a valid email." in errors_arg["email"]

    result = await asyncio.wait_for(form.future, timeout=1)
    assert result is None


@pytest.mark.asyncio
async def test_form_on_submit_bool_conversion(mock_interaction):
    form = ValidationTestForm(ctx=MagicMock())
    form._declared_fields["email"].component_instance.value = "test@example.com"
    form._declared_fields["is_member"].component_instance.value = "yes"

    await form.on_submit(mock_interaction)
    result = await asyncio.wait_for(form.future, timeout=1)
    assert result == {"email": "test@example.com", "is_member": True}

    form = ValidationTestForm(ctx=MagicMock()) # New instance for new future
    form._declared_fields["email"].component_instance.value = "test@example.com"
    form._declared_fields["is_member"].component_instance.value = "0"

    await form.on_submit(mock_interaction)
    result = await asyncio.wait_for(form.future, timeout=1)
    assert result == {"email": "test@example.com", "is_member": False}


@pytest.mark.asyncio
async def test_handle_validation_errors_sends_message(mock_interaction):
    form = SimpleTestForm(ctx=MagicMock())
    errors = {"name": "This is required."}

    # Test when interaction.response is not done
    mock_interaction.response.is_done.return_value = False
    await form.handle_validation_errors(mock_interaction, errors)
    mock_interaction.response.send_message.assert_called_once()
    args, kwargs = mock_interaction.response.send_message.call_args
    assert "Please correct the following errors" in args[0]
    assert "**Your Name**: This is required." in args[0]
    assert kwargs.get("ephemeral") is True

    # Test when interaction.response is done (use followup)
    mock_interaction.response.is_done.return_value = True
    mock_interaction.response.send_message.reset_mock() # Reset for next call
    await form.handle_validation_errors(mock_interaction, errors)
    mock_interaction.followup.send.assert_called_once()
    args_f, kwargs_f = mock_interaction.followup.send.call_args
    assert "Please correct the following errors" in args_f[0]
    assert kwargs_f.get("ephemeral") is True


@pytest.mark.asyncio
async def test_form_on_timeout(mock_context): # Use mock_context for logger
    form = SimpleTestForm(ctx=mock_context)
    # Manually call on_timeout (usually called by discord.py)
    await form.on_timeout()
    assert form.future.done()
    assert await form.future is None # Future should be set to None
    mock_context.bot.logger.info.assert_called() # Check if logger was called

@pytest.mark.asyncio
async def test_form_on_error(mock_interaction):
    form = SimpleTestForm(ctx=MagicMock()) # Mock ctx
    test_exception = ValueError("Test error in process_form_data")

    # Simulate error during process_form_data by patching it
    async def mock_process_error(*args):
        raise test_exception

    form.process_form_data = mock_process_error
    form._declared_fields["name"].component_instance.value = "Test" # Valid input to reach process_form_data

    await form.on_submit(mock_interaction) # This should call on_error internally

    assert form.future.done()
    with pytest.raises(ValueError, match="Test error in process_form_data"):
        await form.future

    # Check if on_error tried to send a message
    # on_error itself calls super().on_error, so direct send_message might not be there
    # but it should have set the future with an exception
    # If on_error sends a message:
    # mock_interaction.response.send_message.assert_called() or mock_interaction.followup.send.assert_called()


# --- Test EnhancedContext.ask_form helper ---
@pytest.mark.asyncio
async def test_ask_form_success(mock_context):
    # Mock the form class that ask_form will instantiate
    MockFormClass = MagicMock(spec=DispyplusForm)
    mock_form_instance = MockFormClass.return_value

    # Setup the future on the mocked form instance
    # This future will be awaited by ask_form
    mock_form_instance.future = asyncio.Future()
    expected_data = {"key": "value"}
    mock_form_instance.future.set_result(expected_data)

    # Call ask_form
    # Need to use patch for inspect.signature if form_class is a MagicMock
    # and __init__ signature is inspected.
    with patch('inspect.signature') as mock_signature:
        # Simulate a signature that doesn't require 'ctx' to avoid complexity,
        # or one that does and ensure 'ctx' is passed.
        # For simplicity, assume no 'ctx' in this specific mock's __init__ for now.
        mock_signature.return_value = MagicMock(parameters={})

        result = await mock_context.ask_form(MockFormClass, title="Test Modal")

    # Assertions
    MockFormClass.assert_called_once_with(title="Test Modal", timeout=180.0) # Default timeout
    mock_context.interaction.response.send_modal.assert_called_once_with(mock_form_instance)
    assert result == expected_data


@pytest.mark.asyncio
async def test_ask_form_timeout(mock_context):
    MockFormClass = MagicMock(spec=DispyplusForm)
    mock_form_instance = MockFormClass.return_value
    mock_form_instance.future = asyncio.Future()
    mock_form_instance.future.set_result(None) # Simulate timeout (form sets future to None)

    with patch('inspect.signature') as mock_signature:
        mock_signature.return_value = MagicMock(parameters={})
        result = await mock_context.ask_form(MockFormClass)

    assert result is None

@pytest.mark.asyncio
async def test_ask_form_exception_in_form(mock_context):
    MockFormClass = MagicMock(spec=DispyplusForm)
    mock_form_instance = MockFormClass.return_value
    mock_form_instance.future = asyncio.Future()
    test_error = ValueError("Form processing failed")
    mock_form_instance.future.set_exception(test_error)

    with patch('inspect.signature') as mock_signature:
        mock_signature.return_value = MagicMock(parameters={})
        with pytest.raises(ValueError, match="Form processing failed"):
            await mock_context.ask_form(MockFormClass)

    mock_context.bot.logger.error.assert_called() # Check if error was logged by ask_form

# TODO: Add tests for TextInputFormField specific properties if any beyond BaseFormField
# TODO: Test BaseFormField abstract methods if they were concrete (they are not, so test via TextInputFormField)
# TODO: Test text_field helper function creates TextInputFormField correctly (implicitly done by form tests)
