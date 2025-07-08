from typing import Dict, Any, Callable, Optional, Type, List, Tuple, Union
import discord
import inspect # For metaclass field collection

# --- Field Definition ---
class FormField:
    def __init__(self,
                 label: str,
                 style: discord.TextStyle = discord.TextStyle.short,
                 placeholder: Optional[str] = None,
                 required: bool = True,
                 default: Optional[str] = None,
                 min_length: Optional[int] = None,
                 max_length: Optional[int] = None,
                 # validator: Optional[Callable[[Any], bool]] = None, # Placeholder for future
                 # validation_error_message: Optional[str] = None, # Placeholder for future
                 # target_type: Optional[Type] = str # Placeholder for future
                ):
        self.label = label
        self.style = style
        self.placeholder = placeholder
        self.required = required
        self.default = default
        self.min_length = min_length
        self.max_length = max_length
        # self.validator = validator
        # self.validation_error_message = validation_error_message
        # self.target_type = target_type

        # This will hold the actual TextInput component instance
        self.text_input_instance: Optional[discord.ui.TextInput] = None
        self.field_name: Optional[str] = None # Will be set by the metaclass

    def to_discord_text_input(self) -> discord.ui.TextInput:
        # Creates and returns a discord.ui.TextInput component based on the field's definition
        return discord.ui.TextInput(
            label=self.label,
            style=self.style,
            placeholder=self.placeholder,
            required=self.required,
            default=self.default,
            min_length=self.min_length,
            max_length=self.max_length,
            custom_id=f"form_field_{self.field_name}" # Ensure custom_id is unique if needed
        )

# Helper function to make field definition more concise
def field(*args, **kwargs) -> FormField:
    return FormField(*args, **kwargs)

# --- Metaclass to collect FormFields ---
class FormMeta(type(discord.ui.Modal)): # Inherit from Modal's metaclass if it has one, else type
    def __new__(mcs, name, bases, attrs):
        declared_fields: Dict[str, FormField] = {}
        for key, value in attrs.items():
            if isinstance(value, FormField):
                value.field_name = key # Assign the attribute name to the field
                declared_fields[key] = value

        attrs['_declared_fields'] = declared_fields
        # Remove fields from class attributes to prevent conflict with Modal's properties
        for key in declared_fields:
            if key in attrs:
                del attrs[key]

        new_cls = super().__new__(mcs, name, bases, attrs)
        return new_cls

# --- Base Form Class ---
class DispyplusForm(discord.ui.Modal, metaclass=FormMeta):
    # _declared_fields will be populated by the metaclass
    _declared_fields: Dict[str, FormField]

    def __init__(self,
                 # ctx: "EnhancedContext", # Assuming EnhancedContext for future use
                 title: Optional[str] = None,
                 timeout: Optional[float] = 180.0
                ):
        # If title is not provided, try to use class-level 'form_title' or class name
        actual_title = title or getattr(self, 'form_title', self.__class__.__name__)
        super().__init__(title=actual_title, timeout=timeout)
        # self.ctx = ctx # Store context if needed for callbacks or validation

        self._build_fields()

    def _build_fields(self):
        # Iterate over a sorted list of fields if order matters, e.g., by definition order
        # For simplicity, direct iteration is used here.
        for field_name, form_field_def in self._declared_fields.items():
            # Create the TextInput and store it back in the FormField instance for value retrieval
            form_field_def.text_input_instance = form_field_def.to_discord_text_input()
            self.add_item(form_field_def.text_input_instance)

    async def on_submit(self, interaction: discord.Interaction):
        data: Dict[str, Any] = {}
        # validation_errors = {} # For future validation logic

        for field_name, field_def in self._declared_fields.items():
            if field_def.text_input_instance:
                value = field_def.text_input_instance.value
                # TODO: Type conversion based on field_def.target_type
                # TODO: Validation based on field_def.validator
                data[field_name] = value
            else:
                # This case should ideally not happen if _build_fields is correct
                data[field_name] = None

        # if validation_errors:
        #     await self.handle_validation_errors(interaction, validation_errors)
        #     return

        await self.process_form_data(interaction, data)

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
        # Basic error handling
        # Log the error (assuming a logger is available, e.g., self.ctx.bot.logger)
        print(f"Error in DispyplusForm: {error}") # Basic print for prototype
        if not interaction.response.is_done():
            await interaction.response.send_message("An error occurred while processing the form.", ephemeral=True)
        else:
            await interaction.followup.send("An error occurred while processing the form.", ephemeral=True)
        self.stop()

    async def on_timeout(self) -> None:
        # Basic timeout handling
        # Log timeout (assuming logger)
        print(f"Form '{self.title}' timed out.") # Basic print for prototype
        # Optionally, try to inform the user if the interaction object is still valid (usually not for modal timeout)
        self.stop()


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
