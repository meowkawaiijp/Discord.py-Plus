from typing import Dict, Any, Callable, Optional, Type, List, Tuple, Union
import discord
import inspect # For metaclass field collection

# --- Field Definition ---

# TODO: Explore making FormField a base class and having TextInputField, SelectField etc. inherit from it
# if discord.py Modals ever support more than TextInputs.
# For now, FormField is effectively a TextInputField.

class BaseFormField: # New base class for future field types
    def __init__(self, label: str, required: bool = True,
                 validator: Optional[Callable[[Any, discord.Interaction], Union[bool, Tuple[bool, str]]]] = None,
                 validation_error_message: Optional[str] = "Invalid input."):
        self.label = label
        self.required = required
        self.validator = validator
        self.validation_error_message = validation_error_message
        self.field_name: Optional[str] = None # Set by metaclass
        self.component_instance: Optional[discord.ui.Item] = None # Generic component instance

    def create_discord_component(self) -> discord.ui.Item:
        # This method should be implemented by subclasses (e.g., TextInputFormField)
        raise NotImplementedError("Subclasses must implement create_discord_component")

    def get_value_from_component(self) -> Any:
        # This method should be implemented by subclasses
        raise NotImplementedError("Subclasses must implement get_value_from_component")

    def get_target_type(self) -> Optional[Type]:
        # This method should be implemented by subclasses if they have a target_type
        return str # Default or raise NotImplementedError

class TextInputFormField(BaseFormField):
    def __init__(self,
                 label: str,
                 style: discord.TextStyle = discord.TextStyle.short,
                 placeholder: Optional[str] = None,
                 required: bool = True,
                 default: Optional[str] = None,
                 min_length: Optional[int] = None,
                 max_length: Optional[int] = None,
                 validator: Optional[Callable[[Any, discord.Interaction], Union[bool, Tuple[bool, str]]]] = None,
                 validation_error_message: Optional[str] = "Invalid input.",
                 target_type: Optional[Type] = str
                ):
        super().__init__(label, required, validator, validation_error_message)
        self.style = style
        self.placeholder = placeholder
        self.default = default
        self.min_length = min_length
        self.max_length = max_length
        self.target_type = target_type
        # component_instance will be discord.ui.TextInput

    def create_discord_component(self) -> discord.ui.TextInput:
        return discord.ui.TextInput(
            label=self.label,
            style=self.style,
            placeholder=self.placeholder,
            required=self.required,
            default=self.default,
            min_length=self.min_length,
            max_length=self.max_length,
            custom_id=f"form_field_text_{self.field_name}"
        )

    def get_value_from_component(self) -> Optional[str]:
        if isinstance(self.component_instance, discord.ui.TextInput):
            return self.component_instance.value
        return None # Should not happen if setup correctly

    def get_target_type(self) -> Optional[Type]:
        return self.target_type

# Helper function to make field definition more concise (specifically for TextInput for now)
def text_field(*args, **kwargs) -> TextInputFormField: # Renamed from field to text_field
    return TextInputFormField(*args, **kwargs)

# TODO: Add select_field helper when/if Modals support Selects
# def select_field(label: str, options: List[discord.SelectOption], ..., target_type: Optional[Type] = str) -> SelectFormField:
#     return SelectFormField(...)


# --- Metaclass to collect FormFields ---
class FormMeta(type(discord.ui.Modal)):
    def __new__(mcs, name, bases, attrs):
        declared_fields: Dict[str, BaseFormField] = {} # Now expects BaseFormField or its children
        for key, value in attrs.items():
            if isinstance(value, BaseFormField):
                value.field_name = key
                declared_fields[key] = value

        attrs['_declared_fields'] = declared_fields
        for key in declared_fields:
            if key in attrs:
                del attrs[key]

        new_cls = super().__new__(mcs, name, bases, attrs)
        return new_cls

# --- Base Form Class ---
class DispyplusForm(discord.ui.Modal, metaclass=FormMeta):
    # _declared_fields will be populated by the metaclass
    _declared_fields: Dict[str, BaseFormField] # Uses BaseFormField
    form_title: Optional[str] = None # Class variable for default title

    def __init__(self,
                 ctx: Optional[Any] = None, # Optional EnhancedContext for future use (e.g. logging)
                 title: Optional[str] = None,
                 timeout: Optional[float] = 180.0,
                 **kwargs # For future form-specific init args
                ):
        # Determine title: explicit > class var > class name
        actual_title = title or self.form_title or self.__class__.__name__
        super().__init__(title=actual_title, timeout=timeout)

        self.ctx = ctx # Store context if provided
        self.future: asyncio.Future[Optional[Dict[str, Any]]] = asyncio.Future()
        self._build_fields()

    def _build_fields(self):
        for field_name, form_field_def in self._declared_fields.items():
            # Create the discord component (e.g., TextInput)
            discord_component = form_field_def.create_discord_component()
            # Store the component instance back into the field definition object
            form_field_def.component_instance = discord_component
            self.add_item(discord_component) # Add to the Modal

    async def on_submit(self, interaction: discord.Interaction):
        data: Dict[str, Any] = {}
        validation_errors: Dict[str, str] = {}

        for field_name, field_def in self._declared_fields.items():
            if not field_def.component_instance:
                validation_errors[field_name] = "Form field component not initialized."
                continue

            # Get raw value using the generalized method from field definition
            raw_value = field_def.get_value_from_component()

            # If raw_value is None (e.g. get_value_from_component failed or not applicable for a future field type)
            # and the field is required, this might be an issue. For TextInput, value is always str.
            if raw_value is None and field_def.required: # Should not happen with current TextInputFormField
                validation_errors[field_name] = f"{field_def.label} could not retrieve a value."
                continue

            # Ensure raw_value is a string for text-based processing, if it's not None
            # For future field types (like Select), raw_value might not always be a string.
            # This part might need adjustment when other field types are added.
            raw_value_str = str(raw_value) if raw_value is not None else ""


            if field_def.required and not raw_value_str.strip():
                validation_errors[field_name] = f"{field_def.label} is required."
                continue

            if not field_def.required and not raw_value_str.strip():
                data[field_name] = None
                target_type = field_def.get_target_type()
                if target_type is bool:
                    data[field_name] = False
                continue

            target_type = field_def.get_target_type()
            converted_value: Any = None
            try:
                if target_type is bool:
                    if raw_value_str.lower() in ['true', 'yes', '1', 'on']:
                        converted_value = True
                    elif raw_value_str.lower() in ['false', 'no', '0', 'off']:
                        converted_value = False
                    else:
                        if field_def.required:
                             raise ValueError("Must be a boolean value (true/false, yes/no, etc.).")
                elif target_type: # Includes str, int, float etc.
                    converted_value = target_type(raw_value_str)
                else: # No target_type specified by field, should default to something (e.g. str in BaseFormField)
                    converted_value = raw_value_str
            except ValueError as e:
                validation_errors[field_name] = f"Invalid type for {field_def.label}. Expected {target_type.__name__ if target_type else 'string'} (e.g., '{raw_value_str}' -> {str(e)})."
                continue
            except Exception as e:
                validation_errors[field_name] = f"Error converting value for {field_def.label}: {str(e)}"
                continue

            if field_def.validator:
                try:
                    validation_result = field_def.validator(converted_value, interaction)
                    is_valid = False
                    custom_error_msg = None
                    if isinstance(validation_result, tuple):
                        is_valid, custom_error_msg = validation_result
                    elif isinstance(validation_result, bool):
                        is_valid = validation_result
                    if not is_valid:
                        validation_errors[field_name] = custom_error_msg or field_def.validation_error_message or "Validation failed."
                except Exception as e:
                    validation_errors[field_name] = f"Error during validation for {field_def.label}: {str(e)}"

            if field_name not in validation_errors:
                data[field_name] = converted_value

        if validation_errors:
            await self.handle_validation_errors(interaction, validation_errors)
            # Do not set future result if validation failed, or set it to an error indicator
            # For now, we assume handle_validation_errors sends a message and that's it.
            # The future will remain pending until timeout or explicit cancellation if not set.
            # Or, we can set an exception to the future.
            # For simplicity, let's not complete the future here, let it timeout or be handled by on_error.
            # However, if process_form_data is NOT called, the future won't be set with data.
            # A common pattern is to set an exception on the future for validation errors.
            # Let's try setting None and letting the caller check.
            if not self.future.done():
                 self.future.set_result(None) # Indicate failure to process due to validation
            return

        try:
            await self.process_form_data(interaction, data)
            # If process_form_data doesn't set the future, set it with data here.
            # It's better if process_form_data is responsible for setting future on success.
            # For now, assume process_form_data will call self.future.set_result(data) or similar.
            # If it doesn't, the form will hang until timeout for the caller.
            # Let's add a default: if future not set by process_form_data, set it here.
            if not self.future.done():
                self.future.set_result(data)
        except Exception as e:
            # Error within user's process_form_data
            if hasattr(self.ctx, 'bot') and hasattr(self.ctx.bot, 'logger') and self.ctx.bot.logger: # Check logger exists
                 self.ctx.bot.logger.error(f"Error in user's process_form_data for {self.title}: {e}", exc_info=True)
            if not self.future.done():
                self.future.set_exception(e) # Set exception on the future
            # Also call on_error to inform the user via Discord if possible
            # Check if interaction is passed to on_error, if not, we might not be able to respond to user
            await self.on_error(interaction, e) # Ensure interaction is passed to on_error

        # After processing, if part of a wizard, notify the wizard.
        if self.wizard_controller and hasattr(self.wizard_controller, 'on_step_complete'):
            # The interaction object here is the one that submitted THIS modal.
            # The wizard needs this to potentially defer and then control the next step.
            self.wizard_controller.on_step_complete(interaction, data if not validation_errors else None)


    async def handle_validation_errors(self, interaction: discord.Interaction, errors: Dict[str, str]):
        error_message_lines = ["Please correct the following errors and try submitting again:"]
        for field_label_or_name, err_msg in errors.items():
            # Try to get the proper label for the field
            field_label = field_label_or_name
            if field_label_or_name in self._declared_fields:
                field_label = self._declared_fields[field_label_or_name].label
            error_message_lines.append(f"- **{field_label}**: {err_msg}")

        full_error_message = "\n".join(error_message_lines)

        # Ensure message is not too long for Discord
        if len(full_error_message) > 2000:
            full_error_message = full_error_message[:1990] + "... (too many errors to display fully)"

        if not interaction.response.is_done():
            await interaction.response.send_message(full_error_message, ephemeral=True)
        else:
            # This case is less ideal as the modal is gone. A followup is the best we can do.
            await interaction.followup.send(full_error_message, ephemeral=True)


    async def process_form_data(self, interaction: discord.Interaction, data: Dict[str, Any]):
        # User implements this method in their subclass
        # Default implementation for testing
        response_lines = [f"Form '{self.title}' Submitted:"]
        for key, value in data.items():
            response_lines.append(f"- {key}: {value}")
        await interaction.response.send_message("\n".join(response_lines), ephemeral=True)

    # async def handle_validation_errors(self, interaction: discord.Interaction, errors: Dict[str, str]):
    #     # Placeholder for future
    #     error_message = "Please correct the following errors:\n" + "\n".join(f"- {field}: {err}" for field, err in errors.items())
    #     # This needs careful handling with Modal's interaction lifecycle
    #     if not interaction.response.is_done():
    #         await interaction.response.send_message(error_message, ephemeral=True) # This might not be the right way for modals
    #     else:
    #         await interaction.followup.send(error_message, ephemeral=True)


    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        # Log the error
        if hasattr(self.ctx, 'bot') and hasattr(self.ctx.bot, 'logger'):
            self.ctx.bot.logger.error(f"Error in DispyplusForm '{self.title}': {error}", exc_info=True)
        else: # Fallback basic print
            print(f"Error in DispyplusForm '{self.title}': {error}")

        if not self.future.done():
            self.future.set_exception(error)

        # Try to inform the user if the interaction is still valid
        if interaction and not interaction.response.is_done():
            try:
                await interaction.response.send_message("An unexpected error occurred while processing the form. Please try again later.", ephemeral=True)
            except discord.HTTPException:
                pass # Failed to send error response
        elif interaction: # Response already done, try followup
            try:
                await interaction.followup.send("An unexpected error occurred. Please try again later.", ephemeral=True)
            except discord.HTTPException:
                pass

        super().on_error(interaction, error) # Call Modal's on_error if it has specific logic
        # self.stop() is usually called by Modal's on_error or should be if overriding.

    async def on_timeout(self) -> None:
        # Log timeout
        if hasattr(self.ctx, 'bot') and hasattr(self.ctx.bot, 'logger'):
            self.ctx.bot.logger.info(f"DispyplusForm '{self.title}' timed out.")
        else: # Fallback basic print
            print(f"DispyplusForm '{self.title}' timed out.")

        if not self.future.done():
            self.future.set_result(None) # Indicate timeout with None

        # If this form is part of a wizard, notify the wizard
        if hasattr(self, 'wizard_controller') and self.wizard_controller:
             # Need a way for wizard to handle step timeout
             # self.wizard_controller.on_step_timeout(self) # Conceptual
             pass

        super().on_timeout()

    # Property to potentially link to a wizard
    @property
    def wizard_controller(self) -> Optional[Any]: # Use 'WizardController' type if importable
        return getattr(self, '_wizard_controller', None)

    @wizard_controller.setter
    def wizard_controller(self, controller: Optional[Any]):
        self._wizard_controller = controller


# --- Example Usage (for testing, would be in a Cog or bot command) ---
# This part is conceptual and would be integrated into a bot.
if __name__ == '__main__': # This block is for conceptual testing only

    class MyExampleForm(DispyplusForm):
        form_title = "My Test Form" # Class-level title

        user_name: str = field(label="Your Name", placeholder="Enter your full name", required=True, max_length=50)
        feedback: Optional[str] = field(label="Your Feedback", style=discord.TextStyle.long, required=False)
        email: str = field(label="Email Address", placeholder="user@example.com")

    # How it might be used in a command:
    # @bot.command()
    # async def open_my_form(ctx: EnhancedContext):
    #     form = MyExampleForm(ctx) # Pass context if needed by form
    #     await ctx.interaction.response.send_modal(form) # Assuming slash command context

    # To run this prototype, you'd need a running bot and a command to trigger the modal.
    # The core logic is in DispyplusForm and FormField.
    pass
