import asyncio
from typing import List, Type, Dict, Any, Optional, Union
import discord
from .forms import DispyplusForm

class WizardStep:

    def __init__(self, form_class: Type[DispyplusForm], title: Optional[str]=None, **form_kwargs: Any):
        self.form_class = form_class
        self.title = title
        self.form_kwargs = form_kwargs

class WizardController:

    def __init__(self, steps: List[WizardStep]):
        if not steps:
            raise ValueError('Wizard must have at least one step.')
        self.steps = steps
        self.current_step_index: int = 0
        self.collected_data: Dict[str, Any] = {}
        self.future: asyncio.Future[Optional[Dict[str, Any]]] = asyncio.Future()
        self._current_interaction: Optional[discord.Interaction] = None
        self._initial_interaction_responded: bool = False

    async def start(self, interaction: discord.Interaction):
        if not interaction:
            raise ValueError('An initial interaction is required to start the wizard.')
        self._current_interaction = interaction
        await self._next_step()

    async def _next_step(self):
        if self._current_interaction is None:
            if not self.future.done():
                self.future.set_exception(RuntimeError('Wizard lost interaction context.'))
            return
        if self.current_step_index >= len(self.steps):
            if not self.future.done():
                self.future.set_result(self.collected_data)
            return
        step_info = self.steps[self.current_step_index]
        form_instance = step_info.form_class(title=step_info.title, **step_info.form_kwargs)
        try:
            if not self._initial_interaction_responded:
                await self._current_interaction.response.send_modal(form_instance)
                self._initial_interaction_responded = True
            elif self._current_interaction.response.is_done():
                print('WizardController Error: Cannot send subsequent modal on the same deferred interaction without a new trigger.')
                if not self.future.done():
                    self.future.set_result(None)
                return
            else:
                await self._current_interaction.response.send_modal(form_instance)
            form_data = await form_instance.future
            if form_data is not None:
                self.collected_data.update(form_data)
                self.current_step_index += 1
                await self._next_step()
            elif not self.future.done():
                self.future.set_result(None)
        except discord.errors.InteractionResponded:
            print(f'WizardController Error: Interaction for step {self.current_step_index} was already responded to.')
            if hasattr(self._current_interaction.client, 'logger'):
                self._current_interaction.client.logger.warning('Wizard: Interaction already responded to when trying to send next modal.')
            if not self.future.done():
                self.future.set_result(None)
        except Exception as e:
            print(f'Error in wizard step {self.current_step_index}: {e}')
            if hasattr(self._current_interaction.client, 'logger'):
                self._current_interaction.client.logger.error(f'Wizard error: {e}', exc_info=True)
            if not self.future.done():
                self.future.set_exception(e)

    def on_step_complete(self, interaction_for_next_step: discord.Interaction, data: Optional[Dict[str, Any]]):
        self._current_interaction = interaction_for_next_step
        if data is not None:
            self.collected_data.update(data)
            self.current_step_index += 1
            asyncio.create_task(self._next_step_from_callback())
        elif not self.future.done():
            self.future.set_result(None)

    async def _next_step_from_callback(self):
        """Helper to call _next_step from the callback, ensuring it's awaited correctly."""
        if self._current_interaction and (not self._current_interaction.response.is_done()):
            try:
                await self._current_interaction.response.defer(ephemeral=True, thinking=False)
            except discord.errors.InteractionResponded:
                pass
            except Exception as e:
                print(f'Wizard: Error deferring interaction for next step: {e}')
                if not self.future.done():
                    self.future.set_exception(e)
                return
        print("WizardController: _next_step_from_callback reached. Due to Discord interaction limitations, true multi-modal wizards from a single command interaction are complex and typically require intermediate component interactions (e.g., buttons). This prototype's current sequential modal logic will not work as is beyond the first step without such a redesign.")
        if self.current_step_index >= len(self.steps):
            if not self.future.done():
                self.future.set_result(self.collected_data)

    async def get_wizard_result(self):
        return await self.future
