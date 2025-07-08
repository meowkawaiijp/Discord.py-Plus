import asyncio
from typing import List, Type, Dict, Any, Optional, Union
import discord

from .forms import DispyplusForm
# Assuming EnhancedContext is available for type hinting if needed for ctx
# from ..core.context import EnhancedContext # If passed to start method

class WizardStep:
    """
    Represents a single step in the wizard, typically a DispyplusForm.
    """
    def __init__(self, form_class: Type[DispyplusForm], title: Optional[str] = None, **form_kwargs: Any):
        self.form_class = form_class
        self.title = title
        self.form_kwargs = form_kwargs # Additional kwargs to pass to the form's __init__

class WizardController:
    """
    Manages a sequence of DispyplusForm steps to create a multi-step form wizard.
    """
    def __init__(self, steps: List[WizardStep]):
        if not steps:
            raise ValueError("Wizard must have at least one step.")
        self.steps = steps
        self.current_step_index: int = 0
        self.collected_data: Dict[str, Any] = {}
        self.future: asyncio.Future[Optional[Dict[str, Any]]] = asyncio.Future()

        self._current_interaction: Optional[discord.Interaction] = None
        self._initial_interaction_responded: bool = False # Track if initial interaction has been responded to

    async def start(self, interaction: discord.Interaction): # Takes the initial interaction
        if not interaction:
            raise ValueError("An initial interaction is required to start the wizard.")
        self._current_interaction = interaction
        await self._next_step()

    async def _next_step(self):
        if self._current_interaction is None:
            # This should not happen if logic is correct
            if not self.future.done(): self.future.set_exception(RuntimeError("Wizard lost interaction context."))
            return

        if self.current_step_index >= len(self.steps):
            # All steps completed
            if not self.future.done(): self.future.set_result(self.collected_data)
            return

        step_info = self.steps[self.current_step_index]

        # Prepare form instance
        # Pass the wizard's context (ctx) if the form expects it, or specific required args
        # For now, DispyplusForm init takes optional ctx.
        # If forms need access to overall wizard data or control, that needs more design.
        form_instance = step_info.form_class(
            title=step_info.title,
            **step_info.form_kwargs
            # ctx=self._current_interaction.client. # How to get EnhancedContext here if needed by form?
            # This implies forms used in wizards might not always get an EnhancedContext directly,
            # or the WizardController needs to be created with one. For now, forms are self-contained.
        )

        try:
            # How to display the modal depends on the interaction state
            if not self._initial_interaction_responded:
                # This is the first modal in the sequence for this interaction
                await self._current_interaction.response.send_modal(form_instance)
                self._initial_interaction_responded = True # Mark that initial response has been used
            else:
                # For subsequent modals, we cannot use interaction.response.send_modal again.
                # This is the main challenge for multi-step modals with a single initial interaction.
                # Option 1: Use followup.send_modal (if discord.py adds this - NOT CURRENTLY AVAILABLE)
                # Option 2: Send a message with a button that triggers the next modal (multi-interaction)
                # Option 3: (Hacky) Edit the original response to show a temporary message, then somehow
                #           trigger a new interaction to show the next modal.
                # For this prototype, we'll assume a limitation or explore if a new interaction is needed.
                # Let's try a conceptual approach assuming we can somehow present the next modal.
                # This part WILL LIKELY FAIL with current discord.py if not handled carefully.
                # A common pattern is that the on_submit of the *previous* modal defers,
                # and then the Wizard does something. But the Wizard needs control flow.

                # If the previous modal's on_submit did interaction.response.defer(),
                # we might be able to use interaction.followup to send a message,
                # but not another modal directly from the same initial interaction.

                # WORKAROUND/SIMPLIFICATION for prototype:
                # We will assume for now that the interaction object passed to _next_step
                # is always "fresh" enough or has been correctly managed by the previous step's
                # on_submit (e.g., by deferring and the wizard is called immediately after).
                # This is a significant simplification of Discord's interaction model.
                # A robust solution would involve an intermediate message with a button.

                # If the interaction was deferred by the form's on_submit:
                if self._current_interaction.response.is_done(): # deferred
                     # We cannot send another modal as a direct response or followup to the *same* interaction.
                     # This is where the wizard flow breaks with a single interaction.
                     # The wizard would need to manage a new interaction for each step (e.g. button click).

                     # For this prototype, we'll just log an error and end the wizard if we hit this.
                     print("WizardController Error: Cannot send subsequent modal on the same deferred interaction without a new trigger.")
                     if not self.future.done(): self.future.set_result(None) # Indicate wizard failure
                     return
                else: # This path should not be taken if previous was a modal.
                    await self._current_interaction.response.send_modal(form_instance)


            # Wait for the form to complete (its own future)
            form_data = await form_instance.future

            if form_data is not None:
                self.collected_data.update(form_data) # Merge data
                self.current_step_index += 1
                # The interaction object in form_instance.future's callback (on_submit)
                # is the one that submitted *that specific modal*. We need to use that
                # for deferring if we want to continue the chain.
                # This implies the WizardController needs to be more tightly integrated with the form's lifecycle,
                # or the form needs to call back to the wizard.

                # Let's assume the form's on_submit, after setting its future,
                # has correctly deferred the interaction it received.
                # The WizardController then needs *that* interaction to proceed.
                # This suggests the form's on_submit should pass the interaction back to the wizard.
                # For now, we'll re-use self._current_interaction but this is a weak point.

                # A better model: form.on_submit calls wizard.on_step_complete(interaction, data)
                # For this prototype, we just proceed.
                await self._next_step() # Try to show the next step
            else:
                # Form timed out, or validation error not leading to data (future set to None)
                # Or user explicitly cancelled (future enhancement)
                if not self.future.done(): self.future.set_result(None) # Wizard failed or was cancelled

        except discord.errors.InteractionResponded:
            # This might happen if we try to send_modal when already responded.
            # This highlights the difficulty of multi-modal sequences.
            print(f"WizardController Error: Interaction for step {self.current_step_index} was already responded to.")
            if hasattr(self._current_interaction.client, 'logger'): # Basic logging
                 self._current_interaction.client.logger.warning("Wizard: Interaction already responded to when trying to send next modal.")
            if not self.future.done(): self.future.set_result(None) # Wizard failure

        except Exception as e:
            print(f"Error in wizard step {self.current_step_index}: {e}")
            if hasattr(self._current_interaction.client, 'logger'):
                 self._current_interaction.client.logger.error(f"Wizard error: {e}", exc_info=True)
            if not self.future.done(): self.future.set_exception(e)

    def on_step_complete(self, interaction_for_next_step: discord.Interaction, data: Optional[Dict[str, Any]]):
        """
        Callback for DispyplusForm to call when it's successfully submitted.
        This method will then manage showing the next step or finishing the wizard.
        """
        self._current_interaction = interaction_for_next_step # IMPORTANT: Update to the new interaction object

        if data is not None:
            self.collected_data.update(data)
            self.current_step_index += 1
            # Use a task to avoid blocking the on_submit of the form
            asyncio.create_task(self._next_step_from_callback())
        else:
            # Form was cancelled or had validation errors not recovered from
            if not self.future.done():
                self.future.set_result(None) # Wizard effectively cancelled

    async def _next_step_from_callback(self):
        """Helper to call _next_step from the callback, ensuring it's awaited correctly."""
        if self._current_interaction and not self._current_interaction.response.is_done():
            # The interaction from the modal submit *must* be responded to.
            # Defer it so we can potentially send another modal or message.
            try:
                await self._current_interaction.response.defer(ephemeral=True, thinking=False) # Defer silently
            except discord.errors.InteractionResponded:
                pass # Already deferred or responded, proceed carefully.
            except Exception as e:
                print(f"Wizard: Error deferring interaction for next step: {e}")
                if not self.future.done(): self.future.set_exception(e)
                return

        # Now that the interaction from the previous modal is deferred,
        # we can't use it to send another modal. This is the core issue.
        # The _next_step logic needs to be re-thought for true multi-modal via single command.

        # For a true wizard with multiple modals from one command, the flow would be:
        # 1. Initial Command -> Interaction1
        # 2. ctx.ask_form(Step1Form) -> sends Modal1 using Interaction1
        # 3. User submits Modal1 -> on_submit gets Interaction2
        # 4. Step1Form.process_form_data:
        #    - Sets its own future (for ask_form to get data of Step1)
        #    - Calls wizard_controller.record_step_data(data)
        #    - Calls wizard_controller.proceed_to_next_step(Interaction2)
        # 5. WizardController.proceed_to_next_step(Interaction2):
        #    - If more steps:
        #        - Creates Step2Form instance
        #        - Uses Interaction2.response.send_modal(Step2Form) -> THIS IS THE PROBLEM.
        #          An interaction can only have one modal response.
        #
        # The only way is if each step is triggered by a NEW interaction (e.g., button click).
        # So, WizardController.start() would send the first modal.
        # Its on_submit, instead of wizard.on_step_complete, would send a *message* with a "Next Step" button.
        # Clicking "Next Step" button creates a new interaction, which then calls wizard.show_next_modal(new_interaction).

        # Given this fundamental limitation, this WizardController prototype needs to be redesigned
        # to use intermediate messages with buttons if it's to work robustly.
        # For now, the current _next_step will likely fail after the first step.
        # We will stop development of WizardController here for this iteration and report this finding.

        # Marking as conceptual end for this prototype due to interaction limitations.
        print("WizardController: _next_step_from_callback reached. Due to Discord interaction limitations, true multi-modal wizards from a single command interaction are complex and typically require intermediate component interactions (e.g., buttons). This prototype's current sequential modal logic will not work as is beyond the first step without such a redesign.")
        if self.current_step_index >= len(self.steps): # If it was the last step that called us
             if not self.future.done(): self.future.set_result(self.collected_data)
        # else: if not last step, we can't proceed with another modal on same interaction path easily.


    # If WizardController is to be used with EnhancedContext.ask_form style,
    # it needs its own "future" like DispyplusForm does, to signal completion of the whole wizard.
    async def get_wizard_result(self):
        return await self.future

# To make WizardController work with DispyplusForm, DispyplusForm needs to know about the wizard.
# Modify DispyplusForm:
# - Add an optional `wizard_controller: Optional[WizardController]` to __init__.
# - In `on_submit`, after `process_form_data` and setting its own future (for `ask_form`),
#   if `self.wizard_controller` exists, call `self.wizard_controller.on_step_complete(interaction, data)`.
# This change is outside the scope of this file but noted for integration.
# For this prototype, we will not modify DispyplusForm yet and focus on WizardController's limitation.
