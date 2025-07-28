"""
Advanced form components for Discord bots using modals and custom validation.
"""

import asyncio
from typing import Any, Callable, Dict, List, Optional, Union
import discord
from discord.ext import commands


class FormField:
    """
    Represents a field in a form with validation and formatting options.
    """
    
    def __init__(
        self,
        name: str,
        label: str,
        *,
        placeholder: str = None,
        default: str = None,
        required: bool = True,
        min_length: int = None,
        max_length: int = None,
        style: discord.TextStyle = discord.TextStyle.short,
        validator: Callable[[str], Union[bool, str]] = None,
        transformer: Callable[[str], Any] = None
    ):
        self.name = name
        self.label = label
        self.placeholder = placeholder
        self.default = default
        self.required = required
        self.min_length = min_length
        self.max_length = max_length
        self.style = style
        self.validator = validator
        self.transformer = transformer
        self.value: Any = None
        self.error: str = None
    
    def validate(self, value: str) -> bool:
        """
        Validate the field value.
        
        Args:
            value: The value to validate
            
        Returns:
            True if valid, False otherwise
        """
        self.error = None
        
        # Check required
        if self.required and not value.strip():
            self.error = f"{self.label} is required"
            return False
        
        # Check length constraints
        if self.min_length is not None and len(value) < self.min_length:
            self.error = f"{self.label} must be at least {self.min_length} characters"
            return False
        
        if self.max_length is not None and len(value) > self.max_length:
            self.error = f"{self.label} must be at most {self.max_length} characters"
            return False
        
        # Custom validation
        if self.validator:
            try:
                result = self.validator(value)
                if isinstance(result, str):
                    self.error = result
                    return False
                elif not result:
                    self.error = f"Invalid value for {self.label}"
                    return False
            except Exception as e:
                self.error = f"Validation error for {self.label}: {str(e)}"
                return False
        
        return True
    
    def transform(self, value: str) -> Any:
        """
        Transform the validated value.
        
        Args:
            value: The value to transform
            
        Returns:
            The transformed value
        """
        if self.transformer:
            try:
                return self.transformer(value)
            except Exception:
                return value
        return value
    
    def to_text_input(self) -> discord.ui.TextInput:
        """
        Convert this field to a Discord TextInput.
        
        Returns:
            Discord TextInput component
        """
        return discord.ui.TextInput(
            label=self.label,
            placeholder=self.placeholder,
            default=self.default,
            required=self.required,
            min_length=self.min_length,
            max_length=self.max_length,
            style=self.style
        )


class Form:
    """
    A form that can contain multiple fields with validation and submission handling.
    """
    
    def __init__(
        self,
        title: str,
        *,
        timeout: float = 300.0,
        custom_id: str = None
    ):
        self.title = title
        self.timeout = timeout
        self.custom_id = custom_id or f"form_{id(self)}"
        self.fields: Dict[str, FormField] = {}
        self.data: Dict[str, Any] = {}
        self.errors: Dict[str, str] = {}
        self.submitted = False
        self.cancelled = False
    
    def add_field(self, field: FormField) -> 'Form':
        """
        Add a field to the form.
        
        Args:
            field: The FormField to add
            
        Returns:
            Self for method chaining
        """
        self.fields[field.name] = field
        return self
    
    def field(
        self,
        name: str,
        label: str,
        **kwargs
    ) -> 'Form':
        """
        Add a field to the form using a fluent interface.
        
        Args:
            name: Field name
            label: Field label
            **kwargs: Additional field options
            
        Returns:
            Self for method chaining
        """
        field = FormField(name, label, **kwargs)
        return self.add_field(field)
    
    def validate(self, data: Dict[str, str]) -> bool:
        """
        Validate all form data.
        
        Args:
            data: Dictionary of field names to values
            
        Returns:
            True if all fields are valid, False otherwise
        """
        self.errors.clear()
        valid = True
        
        for name, field in self.fields.items():
            value = data.get(name, "")
            if not field.validate(value):
                self.errors[name] = field.error
                valid = False
            else:
                field.value = field.transform(value)
        
        return valid
    
    def get_data(self) -> Dict[str, Any]:
        """
        Get the validated and transformed form data.
        
        Returns:
            Dictionary of field names to transformed values
        """
        return {name: field.value for name, field in self.fields.items()}
    
    def get_errors(self) -> Dict[str, str]:
        """
        Get validation errors.
        
        Returns:
            Dictionary of field names to error messages
        """
        return self.errors.copy()
    
    def has_errors(self) -> bool:
        """
        Check if the form has any validation errors.
        
        Returns:
            True if there are errors, False otherwise
        """
        return len(self.errors) > 0
    
    async def show(self, interaction: discord.Interaction) -> Dict[str, Any]:
        """
        Show the form to the user and wait for submission.
        
        Args:
            interaction: The interaction to respond to
            
        Returns:
            Dictionary of form data if submitted, None if cancelled
        """
        modal = FormModal(self)
        await interaction.response.send_modal(modal)
        
        # Wait for form submission
        await modal.wait()
        
        if modal.submitted:
            self.data = self.get_data()
            self.submitted = True
            return self.data
        else:
            self.cancelled = True
            return None


class FormModal(discord.ui.Modal):
    """
    Discord modal implementation for forms.
    """
    
    def __init__(self, form: Form):
        super().__init__(title=form.title, timeout=form.timeout, custom_id=form.custom_id)
        self.form = form
        self.submitted = False
        
        # Add text inputs for each field (max 5 per modal)
        for i, (name, field) in enumerate(form.fields.items()):
            if i >= 5:  # Discord modal limit
                break
            
            text_input = field.to_text_input()
            text_input.custom_id = name
            self.add_item(text_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle form submission."""
        # Collect form data
        data = {}
        for item in self.children:
            if isinstance(item, discord.ui.TextInput):
                data[item.custom_id] = item.value
        
        # Validate form data
        if self.form.validate(data):
            self.submitted = True
            
            # Create success embed
            embed = discord.Embed(
                title="✅ Form Submitted",
                description="Your form has been submitted successfully!",
                color=discord.Color.green()
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            # Create error embed
            embed = discord.Embed(
                title="❌ Form Validation Failed",
                description="Please fix the following errors:",
                color=discord.Color.red()
            )
            
            for field_name, error in self.form.get_errors().items():
                field = self.form.fields[field_name]
                embed.add_field(name=field.label, value=error, inline=False)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        
        self.stop()
    
    async def on_error(self, interaction: discord.Interaction, error: Exception):
        """Handle form errors."""
        embed = discord.Embed(
            title="❌ Form Error",
            description=f"An error occurred while processing your form: {str(error)}",
            color=discord.Color.red()
        )
        
        try:
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except:
            # If we can't respond, try to follow up
            try:
                await interaction.followup.send(embed=embed, ephemeral=True)
            except:
                pass
        
        self.stop()


# Predefined validators
class Validators:
    """Common validators for form fields."""
    
    @staticmethod
    def email(value: str) -> Union[bool, str]:
        """Validate email format."""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, value):
            return "Please enter a valid email address"
        return True
    
    @staticmethod
    def url(value: str) -> Union[bool, str]:
        """Validate URL format."""
        import re
        pattern = r'^https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:#(?:\w*))*)?$'
        if not re.match(pattern, value):
            return "Please enter a valid URL"
        return True
    
    @staticmethod
    def integer(min_val: int = None, max_val: int = None):
        """Validate integer within range."""
        def validator(value: str) -> Union[bool, str]:
            try:
                num = int(value)
                if min_val is not None and num < min_val:
                    return f"Value must be at least {min_val}"
                if max_val is not None and num > max_val:
                    return f"Value must be at most {max_val}"
                return True
            except ValueError:
                return "Please enter a valid integer"
        return validator
    
    @staticmethod
    def float_validator(min_val: float = None, max_val: float = None):
        """Validate float within range."""
        def validator(value: str) -> Union[bool, str]:
            try:
                num = float(value)
                if min_val is not None and num < min_val:
                    return f"Value must be at least {min_val}"
                if max_val is not None and num > max_val:
                    return f"Value must be at most {max_val}"
                return True
            except ValueError:
                return "Please enter a valid number"
        return validator
    
    @staticmethod
    def regex(pattern: str, message: str = "Invalid format"):
        """Validate against a regex pattern."""
        import re
        compiled_pattern = re.compile(pattern)
        
        def validator(value: str) -> Union[bool, str]:
            if not compiled_pattern.match(value):
                return message
            return True
        return validator


# Predefined transformers
class Transformers:
    """Common transformers for form fields."""
    
    @staticmethod
    def integer(value: str) -> int:
        """Transform to integer."""
        return int(value)
    
    @staticmethod
    def float_transformer(value: str) -> float:
        """Transform to float."""
        return float(value)
    
    @staticmethod
    def upper(value: str) -> str:
        """Transform to uppercase."""
        return value.upper()
    
    @staticmethod
    def lower(value: str) -> str:
        """Transform to lowercase."""
        return value.lower()
    
    @staticmethod
    def strip(value: str) -> str:
        """Strip whitespace."""
        return value.strip()
    
    @staticmethod
    def list_transformer(separator: str = ","):
        """Transform to list by splitting on separator."""
        def transformer(value: str) -> List[str]:
            return [item.strip() for item in value.split(separator) if item.strip()]
        return transformer