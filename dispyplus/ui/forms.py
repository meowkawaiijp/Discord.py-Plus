from typing import Dict, Any, Callable, Optional, Type, List, Tuple, Union
import discord
import inspect

class BaseFormField:

    def __init__(self, label: str, required: bool=True, validator: Optional[Callable[[Any, discord.Interaction], Union[bool, Tuple[bool, str]]]]=None, validation_error_message: Optional[str]='Invalid input.'):
        self.label = label
        self.required = required
        self.validator = validator
        self.validation_error_message = validation_error_message
        self.field_name: Optional[str] = None
        self.component_instance: Optional[discord.ui.Item] = None

    def create_discord_component(self) -> discord.ui.Item:
        raise NotImplementedError('Subclasses must implement create_discord_component')

    def get_value_from_component(self) -> Any:
        raise NotImplementedError('Subclasses must implement get_value_from_component')

    def get_target_type(self) -> Optional[Type]:
        return str

class TextInputFormField(BaseFormField):

    def __init__(self, label: str, style: discord.TextStyle=discord.TextStyle.short, placeholder: Optional[str]=None, required: bool=True, default: Optional[str]=None, min_length: Optional[int]=None, max_length: Optional[int]=None, validator: Optional[Callable[[Any, discord.Interaction], Union[bool, Tuple[bool, str]]]]=None, validation_error_message: Optional[str]='Invalid input.', target_type: Optional[Type]=str):
        super().__init__(label, required, validator, validation_error_message)
        self.style = style
        self.placeholder = placeholder
        self.default = default
        self.min_length = min_length
        self.max_length = max_length
        self.target_type = target_type

    def create_discord_component(self) -> discord.ui.TextInput:
        return discord.ui.TextInput(label=self.label, style=self.style, placeholder=self.placeholder, required=self.required, default=self.default, min_length=self.min_length, max_length=self.max_length, custom_id=f'form_field_text_{self.field_name}')

    def get_value_from_component(self) -> Optional[str]:
        if isinstance(self.component_instance, discord.ui.TextInput):
            return self.component_instance.value
        return None

    def get_target_type(self) -> Optional[Type]:
        return self.target_type

def text_field(*args, **kwargs) -> TextInputFormField:
    return TextInputFormField(*args, **kwargs)

class FormMeta(type(discord.ui.Modal)):

    def __new__(mcs, name, bases, attrs):
        declared_fields: Dict[str, BaseFormField] = {}
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

class DispyplusForm(discord.ui.Modal, metaclass=FormMeta):
    _declared_fields: Dict[str, BaseFormField]
    form_title: Optional[str] = None

    def __init__(self, ctx: Optional[Any]=None, title: Optional[str]=None, timeout: Optional[float]=180.0, **kwargs):
        actual_title = title or self.form_title or self.__class__.__name__
        super().__init__(title=actual_title, timeout=timeout)
        self.ctx = ctx
        self.future: asyncio.Future[Optional[Dict[str, Any]]] = asyncio.Future()
        self._build_fields()

    def _build_fields(self):
        for field_name, form_field_def in self._declared_fields.items():
            discord_component = form_field_def.create_discord_component()
            form_field_def.component_instance = discord_component
            self.add_item(discord_component)

    async def on_submit(self, interaction: discord.Interaction):
        data: Dict[str, Any] = {}
        validation_errors: Dict[str, str] = {}
        for field_name, field_def in self._declared_fields.items():
            if not field_def.component_instance:
                validation_errors[field_name] = 'Form field component not initialized.'
                continue
            raw_value = field_def.get_value_from_component()
            if raw_value is None and field_def.required:
                validation_errors[field_name] = f'{field_def.label} could not retrieve a value.'
                continue
            raw_value_str = str(raw_value) if raw_value is not None else ''
            if field_def.required and (not raw_value_str.strip()):
                validation_errors[field_name] = f'{field_def.label} is required.'
                continue
            if not field_def.required and (not raw_value_str.strip()):
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
                    elif field_def.required:
                        raise ValueError('Must be a boolean value (true/false, yes/no, etc.).')
                elif target_type:
                    converted_value = target_type(raw_value_str)
                else:
                    converted_value = raw_value_str
            except ValueError as e:
                validation_errors[field_name] = f"Invalid type for {field_def.label}. Expected {(target_type.__name__ if target_type else 'string')} (e.g., '{raw_value_str}' -> {str(e)})."
                continue
            except Exception as e:
                validation_errors[field_name] = f'Error converting value for {field_def.label}: {str(e)}'
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
                        validation_errors[field_name] = custom_error_msg or field_def.validation_error_message or 'Validation failed.'
                except Exception as e:
                    validation_errors[field_name] = f'Error during validation for {field_def.label}: {str(e)}'
            if field_name not in validation_errors:
                data[field_name] = converted_value
        if validation_errors:
            await self.handle_validation_errors(interaction, validation_errors)
            if not self.future.done():
                self.future.set_result(None)
            return
        try:
            await self.process_form_data(interaction, data)
            if not self.future.done():
                self.future.set_result(data)
        except Exception as e:
            if hasattr(self.ctx, 'bot') and hasattr(self.ctx.bot, 'logger') and self.ctx.bot.logger:
                self.ctx.bot.logger.error(f"Error in user's process_form_data for {self.title}: {e}", exc_info=True)
            if not self.future.done():
                self.future.set_exception(e)
            await self.on_error(interaction, e)
        if self.wizard_controller and hasattr(self.wizard_controller, 'on_step_complete'):
            self.wizard_controller.on_step_complete(interaction, data if not validation_errors else None)

    async def handle_validation_errors(self, interaction: discord.Interaction, errors: Dict[str, str]):
        error_message_lines = ['Please correct the following errors and try submitting again:']
        for field_label_or_name, err_msg in errors.items():
            field_label = field_label_or_name
            if field_label_or_name in self._declared_fields:
                field_label = self._declared_fields[field_label_or_name].label
            error_message_lines.append(f'- **{field_label}**: {err_msg}')
        full_error_message = '\n'.join(error_message_lines)
        if len(full_error_message) > 2000:
            full_error_message = full_error_message[:1990] + '... (too many errors to display fully)'
        if not interaction.response.is_done():
            await interaction.response.send_message(full_error_message, ephemeral=True)
        else:
            await interaction.followup.send(full_error_message, ephemeral=True)

    async def process_form_data(self, interaction: discord.Interaction, data: Dict[str, Any]):
        response_lines = [f"Form '{self.title}' Submitted:"]
        for key, value in data.items():
            response_lines.append(f'- {key}: {value}')
        await interaction.response.send_message('\n'.join(response_lines), ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        if hasattr(self.ctx, 'bot') and hasattr(self.ctx.bot, 'logger'):
            self.ctx.bot.logger.error(f"Error in DispyplusForm '{self.title}': {error}", exc_info=True)
        else:
            print(f"Error in DispyplusForm '{self.title}': {error}")
        if not self.future.done():
            self.future.set_exception(error)
        if interaction and (not interaction.response.is_done()):
            try:
                await interaction.response.send_message('An unexpected error occurred while processing the form. Please try again later.', ephemeral=True)
            except discord.HTTPException:
                pass
        elif interaction:
            try:
                await interaction.followup.send('An unexpected error occurred. Please try again later.', ephemeral=True)
            except discord.HTTPException:
                pass
        super().on_error(interaction, error)

    async def on_timeout(self) -> None:
        if hasattr(self.ctx, 'bot') and hasattr(self.ctx.bot, 'logger'):
            self.ctx.bot.logger.info(f"DispyplusForm '{self.title}' timed out.")
        else:
            print(f"DispyplusForm '{self.title}' timed out.")
        if not self.future.done():
            self.future.set_result(None)
        if hasattr(self, 'wizard_controller') and self.wizard_controller:
            pass
        super().on_timeout()

    @property
    def wizard_controller(self) -> Optional[Any]:
        return getattr(self, '_wizard_controller', None)

    @wizard_controller.setter
    def wizard_controller(self, controller: Optional[Any]):
        self._wizard_controller = controller
if __name__ == '__main__':

    class MyExampleForm(DispyplusForm):
        form_title = 'My Test Form'
        user_name: str = field(label='Your Name', placeholder='Enter your full name', required=True, max_length=50)
        feedback: Optional[str] = field(label='Your Feedback', style=discord.TextStyle.long, required=False)
        email: str = field(label='Email Address', placeholder='user@example.com')
    pass
