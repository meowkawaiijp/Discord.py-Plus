from typing import List, Any, Optional, Union, Callable, AsyncIterator, Tuple, Literal
import discord
import math

from .components import EnhancedView, JumpToPageModal
# from ..core.context import EnhancedContext # Avoid circular import for now, pass ctx as arg

class PaginatorView(EnhancedView):
    """
    A pagination view that supports various content types and data sources.
    """
    def __init__(self,
                 # ctx: "EnhancedContext", # Will be passed to start() or similar
                 data_source: Union[List[Any], AsyncIterator[Any]],
                 items_per_page: int = 10,
                 *,
                 formatter_func: Optional[Callable[[List[Any], int, "PaginatorView"], Union[str, discord.Embed, Tuple[Optional[str], Optional[discord.Embed]]]]] = None,
                 content_type: Literal["embeds", "text_lines", "generic"] = "generic", # Removed "field_groups" for now
                 show_page_buttons: bool = True,
                 show_page_select: bool = False,
                 show_jump_button: bool = False,
                 timeout: Optional[float] = 180.0,
                 author_id: Optional[int] = None # For interaction check
                ):
        super().__init__(timeout=timeout)

        if items_per_page <= 0:
            raise ValueError("items_per_page must be greater than 0.")

        # self.ctx = ctx # Store context if needed for interaction checks not covered by author_id
        self.data_source = data_source
        self.items_per_page = items_per_page
        self.formatter_func = formatter_func
        self.content_type = content_type
        self.show_page_buttons = show_page_buttons
        self.show_page_select = show_page_select
        self.show_jump_button = show_jump_button
        self.author_id = author_id

        self.current_page_number: int = 0
        self.total_pages: Optional[int] = None # Known for lists, unknown for async iterators initially

        self._is_async_iterator = not isinstance(self.data_source, list)
        self._async_buffer: List[Any] = [] # Buffer for async iterator
        self._async_iterator_exhausted: bool = False

        if isinstance(self.data_source, list):
            self.total_pages = math.ceil(len(self.data_source) / self.items_per_page)
            if self.total_pages == 0: # Handle empty list case
                self.total_pages = 1 # Display one empty page

        # To be populated by child classes or formatters
        self.current_page_content: Optional[str] = None
        self.current_page_embed: Optional[discord.Embed] = None
        self.message: Optional[discord.Message] = None # The message this view is attached to

        # Button components
        self.first_page_button: Optional[discord.ui.Button] = None
        self.prev_page_button: Optional[discord.ui.Button] = None
        self.current_page_label_button: Optional[discord.ui.Button] = None # Non-interactive, just a label
        self.next_page_button: Optional[discord.ui.Button] = None
        self.last_page_button: Optional[discord.ui.Button] = None
        self.stop_button: Optional[discord.ui.Button] = None
        self.jump_to_page_button: Optional[discord.ui.Button] = None
        self.page_select_menu: Optional[discord.ui.Select] = None

        # Setup methods should be called after base class __init__ and self attributes are set
        # Call them in send_initial_message or a dedicated setup method if they depend on total_pages
        # For now, let's initialize them here if their respective show_ flags are True.

        current_row_for_controls = 0
        if self.show_page_buttons:
            self._setup_buttons(row=current_row_for_controls)
            current_row_for_controls +=1 # Standard buttons take one row

        # Jump button and Select menu can share a row if both are enabled, or take the next available row.
        # Let's put them on potentially different rows for clarity or if they are standalone.
        # If stop button is on row 1 from _setup_buttons, other controls should be aware.
        # _setup_buttons places stop button on row 1 (if page buttons are shown).
        # Let's adjust row management.

        if self.show_jump_button:
            self._setup_jump_button(row=current_row_for_controls) # If page buttons shown, this is row 1, else row 0
            # If jump button and select menu are on the same row, increment row after both.
            # For now, assume they might be on separate rows or _setup_select_menu handles its own row.

        if self.show_page_select:
            # Determine row for select menu. If jump button also shown, they might share row 1.
            # If only select is shown (no page_buttons, no jump_button), it's row 0.
            # This logic gets complex. A simpler way is to assign fixed rows or a layout manager.
            # For now, assume jump button is on row 1 (if page_buttons on 0), select on row 2.
            # Or, if no page_buttons, jump on 0, select on 1.
            # Let's simplify: if page_buttons, they are on row 0, stop on row 1.
            # Jump and Select can go on row 2.
            select_menu_row = current_row_for_controls if not self.show_jump_button else current_row_for_controls
            if self.show_page_buttons and self.show_jump_button: # std buttons on 0, stop on 1, jump on 1 (if no stop), select on next
                select_menu_row = 1 # Let stop button be on row 2 if these are present
                if self.stop_button: self.stop_button.row = 2 # Move stop button down
            elif self.show_page_buttons: # std buttons on 0, stop on 1
                 select_menu_row = 1 # Select can share row with stop or be next
                 if self.stop_button: self.stop_button.row = 2
            elif self.show_jump_button: # jump on 0
                select_menu_row = 0 # if select shares with jump
            else: # only select
                select_menu_row = 0

            self._setup_page_select_menu(row=select_menu_row)


    def _setup_buttons(self, row: int = 0):
        self.first_page_button = discord.ui.Button(label="|< First", style=discord.ButtonStyle.secondary, custom_id="paginator_first", row=row)
        self.first_page_button.callback = self.go_to_first_page
        self.add_item(self.first_page_button)

        self.prev_page_button = discord.ui.Button(label="< Prev", style=discord.ButtonStyle.primary, custom_id="paginator_prev", row=0)
        self.prev_page_button.callback = self.go_to_previous_page
        self.add_item(self.prev_page_button)

        # This button will be updated with the current page number but is not interactive itself.
        # It's more of a dynamic label.
        self.current_page_label_button = discord.ui.Button(label=f"Page ...", style=discord.ButtonStyle.grey, disabled=True, custom_id="paginator_current_page_label", row=0)
        self.add_item(self.current_page_label_button)

        self.next_page_button = discord.ui.Button(label="Next >", style=discord.ButtonStyle.primary, custom_id="paginator_next", row=0)
        self.next_page_button.callback = self.go_to_next_page
        self.add_item(self.next_page_button)

        self.last_page_button = discord.ui.Button(label="Last >|", style=discord.ButtonStyle.secondary, custom_id="paginator_last", row=0)
        self.last_page_button.callback = self.go_to_last_page
        self.add_item(self.last_page_button)

        # Stop button is now managed based on other controls to determine its row
        # Row calculation for stop_button needs to be robust.
        # Let's assume standard buttons (if shown) are on row 0.
        # Jump/Select (if shown) can be on row 1. Stop on row 2.
        # If only Jump or Select, it's on row 0, Stop on row 1.
        # If no controls, no stop button.

        stop_button_row_candidate = 0
        if self.show_page_buttons:
            stop_button_row_candidate = 1 # After standard nav buttons
        if self.show_jump_button or self.show_page_select:
            # If either jump/select is shown, and page_buttons are also shown, stop goes after jump/select
            # If page_buttons not shown, jump/select are on row 0, stop on row 1
            stop_button_row_candidate = (1 if self.show_page_buttons else 0) + 1

        # Only add stop button if there are other controls or if explicitly requested by show_page_buttons
        # (even if other specific controls like jump/select are off)
        if self.show_page_buttons or self.show_jump_button or self.show_page_select:
            self.stop_button = discord.ui.Button(label="Stop", style=discord.ButtonStyle.danger, custom_id="paginator_stop", row=stop_button_row_candidate)
            self.stop_button.callback = self.stop_pagination
            self.add_item(self.stop_button)


    def _setup_jump_button(self, row: int = 1):
        # Determine row: if page_buttons are shown, they are on row 0, so jump is on row 1.
        # If no page_buttons, jump is on row 0.
        actual_row = 0 if not self.show_page_buttons else 1
        self.jump_to_page_button = discord.ui.Button(label="Jump to Page...", style=discord.ButtonStyle.grey, custom_id="paginator_jump", row=actual_row)
        self.jump_to_page_button.callback = self.prompt_jump_to_page
        self.add_item(self.jump_to_page_button)

    def _setup_page_select_menu(self, row: int = 1):
        # Determine row similarly. If both jump and select, they might share a row or be sequential.
        # If page_buttons: row 0. If jump_button: row 1 (shares with jump if both shown & no page_buttons).
        # This row logic is getting complicated. Let's simplify:
        # Row 0: Standard Nav Buttons (if show_page_buttons)
        # Row 1: Jump Button (if show_jump_button) AND/OR Page Select (if show_page_select)
        # Row 2: Stop Button (if any of above are shown)

        actual_row = 0
        if self.show_page_buttons: actual_row = 1
        # If jump button is also on this row, it's fine, they'll appear next to each other.

        self.page_select_menu = discord.ui.Select(
            placeholder="Select a page...",
            custom_id="paginator_page_select",
            row=actual_row, # Will share row with jump_button if both are on and no page_buttons
            options=[discord.SelectOption(label="Page 1", value="0")] # Dummy option
        )
        self.page_select_menu.callback = self.select_page_from_menu
        self.add_item(self.page_select_menu)


    async def prompt_jump_to_page(self, interaction: discord.Interaction):
        modal = JumpToPageModal(title="Jump to Page", paginator_view=self)
        await interaction.response.send_modal(modal)

    async def select_page_from_menu(self, interaction: discord.Interaction):
        if not self.page_select_menu or not self.page_select_menu.values:
            await interaction.response.defer()
            return

        selected_page_str = self.page_select_menu.values[0]
        try:
            page_to_jump = int(selected_page_str)
            # Validate page_to_jump (0-indexed)
            if self.total_pages is not None and not (0 <= page_to_jump < self.total_pages):
                await interaction.response.send_message(f"Invalid page number. Please choose between 1 and {self.total_pages}.", ephemeral=True)
                return
            elif self.total_pages is None and page_to_jump < 0 : # Async, cannot validate upper bound yet but can check < 0
                 await interaction.response.send_message(f"Invalid page number.", ephemeral=True)
                 return


            self.current_page_number = page_to_jump
            await self._navigate(interaction)
        except ValueError:
            await interaction.response.send_message("Invalid selection.", ephemeral=True)


    async def _update_button_states(self):
        # Update standard buttons
        if self.show_page_buttons and self.first_page_button and self.prev_page_button and self.current_page_label_button and self.next_page_button and self.last_page_button: # Ensure all exist
            is_first_page = self.current_page_number == 0
            self.first_page_button.disabled = is_first_page
            self.prev_page_button.disabled = is_first_page

            page_label_text = f"Page {self.current_page_number + 1}"
            if self.total_pages is not None:
                page_label_text += f"/{self.total_pages}"
            elif self._async_iterator_exhausted:
                if self.total_pages is None: # Should be set by now if exhausted
                    self.total_pages = math.ceil(len(self._async_buffer) / self.items_per_page) if len(self._async_buffer) > 0 else 1
                page_label_text = f"Page {self.current_page_number + 1}/{self.total_pages}"
            else:
                page_label_text += "/?"
            self.current_page_label_button.label = page_label_text

            is_last_page = False
            if self.total_pages is not None:
                is_last_page = self.current_page_number >= self.total_pages - 1
            elif self._async_iterator_exhausted: # Async and exhausted
                # total_pages should be known by now if iterator is exhausted
                is_last_page = self.current_page_number >= (self.total_pages or float('inf')) -1

            self.next_page_button.disabled = is_last_page
            # Disable Last button if total pages unknown AND iterator not exhausted OR if it's the last page
            self.last_page_button.disabled = is_last_page or (self.total_pages is None and not self._async_iterator_exhausted)

        # Update Jump Button state
        if self.show_jump_button and self.jump_to_page_button:
            # Disable if only one page or if total pages unknown and iterator not exhausted (can't validate jump target)
            jump_disabled = (self.total_pages is not None and self.total_pages <= 1) or \
                            (self.total_pages is None and not self._async_iterator_exhausted)
            self.jump_to_page_button.disabled = jump_disabled

        # Update Page Select Menu options and state
        if self.show_page_select and self.page_select_menu:
            current_select_value = str(self.current_page_number)
            new_options: List[discord.SelectOption] = []

            # Determine if select menu should be disabled (e.g., total pages unknown and not exhausted)
            select_disabled = (self.total_pages is None and not self._async_iterator_exhausted and not self._async_buffer) or \
                              (self.total_pages is not None and self.total_pages <= 1)
            self.page_select_menu.disabled = select_disabled
            self.page_select_menu.placeholder = "Select a page..."
            if select_disabled and (self.total_pages is None and not self._async_iterator_exhausted):
                 self.page_select_menu.placeholder = "Page count determining..."
            elif select_disabled and (self.total_pages is not None and self.total_pages <=1):
                 self.page_select_menu.placeholder = "Only one page"


            if not select_disabled and self.total_pages is not None and self.total_pages > 0:
                # Simple case: less than 25 pages, show all
                if self.total_pages <= 25:
                    for i in range(self.total_pages):
                        new_options.append(discord.SelectOption(label=f"Page {i+1}", value=str(i), default=(str(i) == current_select_value)))
                else:
                    # More than 25 pages: create representative page options
                    pages_to_show_indices = set([0, self.total_pages - 1])
                    # Add current page and its immediate neighbors
                    for i in range(max(0, self.current_page_number - 2), min(self.total_pages, self.current_page_number + 3)):
                        pages_to_show_indices.add(i)

                    # Add some spaced out intermediate pages to ensure we don't exceed 25 options easily
                    # Aim for about 5-10 step markers if the range is large enough
                    num_steps = 5
                    if self.total_pages > 50: num_steps = 10 # More steps for very large paginators

                    # Ensure not too many options are generated by steps
                    # Max options for steps = 25 - len(pages_to_show_indices already defined)
                    # This needs to be smarter to avoid overcrowding.
                    # For now, simple step addition if space allows.

                    # Generate interim page numbers, trying to keep total options under 25
                    # Example: 1, ..., current-2, current-1, current, current+1, current+2, ..., last
                    # And some fixed points like 10, 25, 50, 100 if they are far from current group

                    # This simplified logic shows first 5, last 5, and 3 around current if total > 25
                    # This is a placeholder for a more sophisticated range/option generation for large N.
                    if len(pages_to_show_indices) < 25 :
                        for i in range(min(5, self.total_pages)): pages_to_show_indices.add(i)
                    if len(pages_to_show_indices) < 25 :
                         for i in range(max(0, self.total_pages - 5), self.total_pages): pages_to_show_indices.add(i)

                    sorted_pages = sorted(list(pages_to_show_indices))

                    # If still too many, take a slice. This is very basic.
                    if len(sorted_pages) > 25:
                        # Try to keep current page in the view
                        try:
                            current_idx = sorted_pages.index(self.current_page_number)
                            start = max(0, current_idx - 12)
                            end = min(len(sorted_pages), start + 25)
                            if end - start < 25 : start = max(0, end - 25) # Adjust start if end is too short
                            sorted_pages = sorted_pages[start:end]
                        except ValueError: # current page not in list, just take first 25
                            sorted_pages = sorted_pages[:25]


                    for i in sorted_pages:
                        new_options.append(discord.SelectOption(label=f"Page {i+1}", value=str(i), default=(str(i) == current_select_value)))

            elif not select_disabled and self._async_buffer : # Async, but some pages buffered
                 max_buffered_page = math.ceil(len(self._async_buffer) / self.items_per_page)
                 for i in range(min(max_buffered_page, 25)):
                     new_options.append(discord.SelectOption(label=f"Page {i+1}", value=str(i), default=(str(i) == current_select_value)))
                 if max_buffered_page > 25:
                     new_options[-1] = discord.SelectOption(label=f"Page {new_options[-1].label.split(' ')[1]} (more buffered...)", value=new_options[-1].value, default=(new_options[-1].value == current_select_value))


            if not new_options: # Fallback if no options generated
                self.page_select_menu.disabled = True
                new_options.append(discord.SelectOption(label="N/A", value="-1"))

            self.page_select_menu.options = new_options
        elif self.show_page_select and not self.page_select_menu :
             pass # Should have been setup


    async def _get_page_data(self, page_number: int) -> List[Any]:
        """
        Retrieves the data for the given page number.
        Handles both list and async iterator data sources.
        Page number is 0-indexed.
        """
        if page_number < 0:
            # This case should ideally be prevented by button disabling logic
            return []

        if isinstance(self.data_source, list):
            if self.total_pages is not None and page_number >= self.total_pages:
                return [] # Should be prevented by button logic
            start_index = page_number * self.items_per_page
            end_index = start_index + self.items_per_page
            return self.data_source[start_index:end_index]

        elif hasattr(self.data_source, '__aiter__'): # Check if it's an async iterator
            # We need to fetch enough items to fill the buffer up to the requested page
            # This is a simplified approach; for true random access on async iter, it's complex.
            # This implementation assumes sequential access or buffering all previous pages.

            target_end_index = (page_number + 1) * self.items_per_page

            while len(self._async_buffer) < target_end_index and not self._async_iterator_exhausted:
                try:
                    # Type check to satisfy mypy, as self.data_source is Union
                    if hasattr(self.data_source, '__anext__'):
                        item = await self.data_source.__anext__()
                        self._async_buffer.append(item)
                    else: # Should not happen if __aiter__ is present
                        self._async_iterator_exhausted = True
                        break
                except StopAsyncIteration:
                    self._async_iterator_exhausted = True
                    break

            # After buffering, update total_pages if the iterator is exhausted
            if self._async_iterator_exhausted:
                self.total_pages = math.ceil(len(self._async_buffer) / self.items_per_page)
                if self.total_pages == 0: self.total_pages = 1


            start_index = page_number * self.items_per_page
            # Ensure we don't try to access beyond the buffer
            end_index = min(target_end_index, len(self._async_buffer))

            # If start_index is beyond what we could buffer, it means the page is out of bounds
            if start_index >= len(self._async_buffer) and self._async_iterator_exhausted:
                return []

            return self._async_buffer[start_index:end_index]
        else:
            raise TypeError("Unsupported data_source type. Must be a list or an async iterator.")

    async def format_page(self) -> Tuple[Optional[str], Optional[discord.Embed]]:
        """
        Formats the current page data into content and/or embed.
        This method should be overridden by subclasses or a formatter_func should be provided.
        Returns a tuple (content, embed).
        """
        page_data = await self._get_page_data(self.current_page_number)

        page_title = f"Page {self.current_page_number + 1}"
        if self.total_pages is not None:
            page_title += f"/{self.total_pages}"
        else: # For async iterators where total might not be known yet
            if self._async_iterator_exhausted and self.total_pages is None: # Edge case: iterator exhausted but total_pages not yet set
                 self.total_pages = math.ceil(len(self._async_buffer) / self.items_per_page)
                 if self.total_pages == 0: self.total_pages = 1
                 page_title = f"Page {self.current_page_number + 1}/{self.total_pages}"


        if not page_data and self.current_page_number > 0 : # Only consider 'out of bounds' if not the first page potentially being empty
             # Or if it's an async iterator that's exhausted and this page truly has no data
            if isinstance(self.data_source, list) or (self._async_iterator_exhausted and self.current_page_number >= (self.total_pages or 0) ) :
                return ("This page is empty or out of bounds.", discord.Embed(description="No content on this page.", color=discord.Color.orange()),)


        if self.content_type == "embeds":
            if not page_data: # No embeds for this page
                return (None, discord.Embed(title=page_title, description="No embeds on this page.", color=discord.Color.blue()))
            if isinstance(page_data[0], discord.Embed):
                # Assuming one embed per page for this content type for simplicity,
                # or items_per_page is 1. If multiple, this needs adjustment.
                # For now, returning the first embed of the page_data.
                # Users should ensure their data_source for "embeds" provides one embed per "item".
                embed_to_show = page_data[0]
                # Optionally, add page number to the embed footer if not already present
                if embed_to_show.footer.text is None or not (f"Page {self.current_page_number + 1}" in embed_to_show.footer.text):
                    new_footer_text = f"Page {self.current_page_number + 1}"
                    if self.total_pages is not None:
                        new_footer_text += f"/{self.total_pages}"
                    if embed_to_show.footer.text:
                        new_footer_text = f"{embed_to_show.footer.text} - {new_footer_text}"
                    embed_to_show.set_footer(text=new_footer_text, icon_url=embed_to_show.footer.icon_url)
                return (None, embed_to_show)
            else:
                return (None, discord.Embed(title=page_title, description="Invalid data for 'embeds' content type. Expected discord.Embed.", color=discord.Color.red()))

        elif self.content_type == "text_lines":
            embed = discord.Embed(title=page_title, color=discord.Color.blue())
            if not page_data:
                embed.description = "No text lines on this page."
            else:
                # Ensure all items are strings for text_lines
                processed_lines = [str(item) for item in page_data]
                embed.description = "\n".join(processed_lines)

            if len(embed.description) > 4096: # Embed description limit
                embed.description = embed.description[:4093] + "..."
            return (None, embed)

        elif self.content_type == "generic":
            if self.formatter_func:
                try:
                    # Pass the view instance as the third argument to formatter_func
                    formatted_output = self.formatter_func(page_data, self.current_page_number, self)
                    if isinstance(formatted_output, tuple):
                        return (formatted_output[0], formatted_output[1])
                    elif isinstance(formatted_output, discord.Embed):
                        return (None, formatted_output)
                    elif isinstance(formatted_output, str):
                        return (formatted_output, None)
                    else:
                        # Fallback or error for unexpected formatter_func output
                        return (f"Invalid format from formatter_func: {type(formatted_output)}", None)
                except Exception as e:
                    # Log error: self.ctx.bot.logger.error(...)
                    print(f"Error in custom formatter_func: {e}")
                    return (f"Error formatting page: {e}", discord.Embed(title="Formatting Error", description=str(e), color=discord.Color.red()))
            else:
                # Default generic formatting (similar to original fallback)
                embed = discord.Embed(title=page_title, color=discord.Color.greyple())
                description = "\n".join(str(item) for item in page_data)
                if not description:
                    description = "No items on this page."
                embed.description = description[:4096]
                return (None, embed)

        # Should not be reached if content_type is validated
        return ("Invalid content_type specified.", None)


    async def _update_view_internals(self):
        """
        Called after page data is fetched and formatted.
        Updates internal state like current_page_content/embed and button states.
        """
        self.current_page_content, self.current_page_embed = await self.format_page()
        await self._update_button_states()


    async def _navigate(self, interaction: discord.Interaction):
        """Common navigation logic after page number changes."""
        await self._update_view_internals()
        await interaction.response.edit_message(
            content=self.current_page_content,
            embed=self.current_page_embed,
            view=self
        )

    async def go_to_first_page(self, interaction: discord.Interaction):
        if self.current_page_number > 0:
            self.current_page_number = 0
            await self._navigate(interaction)
        else: # Already on first page
            await interaction.response.defer()

    async def go_to_previous_page(self, interaction: discord.Interaction):
        if self.current_page_number > 0:
            self.current_page_number -= 1
            await self._navigate(interaction)
        else: # Already on first page or invalid state
            await interaction.response.defer()

    async def go_to_next_page(self, interaction: discord.Interaction):
        # For async iterators, total_pages might be None initially
        can_go_next = True
        if self.total_pages is not None:
            can_go_next = self.current_page_number < self.total_pages - 1
        elif self._async_iterator_exhausted: # Exhausted and total_pages still None (should not happen)
             can_go_next = False

        if can_go_next:
            # Before incrementing, try to fetch data for the next page to see if it exists
            # This is important for async iterators where the end is not known.
            next_page_data_peek = await self._get_page_data(self.current_page_number + 1)
            if next_page_data_peek: # If there's data for the next page
                self.current_page_number += 1
                await self._navigate(interaction)
            elif self._async_iterator_exhausted: # No next page data and iterator is done
                # This means we are on the true last page. Update button states.
                await self._update_button_states()
                await interaction.response.edit_message(view=self) # Re-edit to update button states if changed
            else: # No next page data, but iterator not exhausted (should not happen if _get_page_data is correct)
                await interaction.response.defer()
        else: # Already on last page or invalid state
            await interaction.response.defer()


    async def go_to_last_page(self, interaction: discord.Interaction):
        if self.total_pages is None and not self._async_iterator_exhausted:
            # If total pages is unknown (async iterator), we need to fetch all data.
            # This can be slow. A progress message might be good for long operations.
            # Let's send a thinking message if it might take time.
            deferred = False
            if not interaction.response.is_done():
                # Estimate if fetching all might be slow. If buffer is small and no total_pages, it might.
                # This is a heuristic. A more robust way would be to count items if possible or use a config threshold.
                if len(self._async_buffer) < 5 * self.items_per_page : # Simple heuristic
                    await interaction.response.defer() # Defer if it seems like it could be long
                    deferred = True

            # Efficiently exhaust the iterator
            while not self._async_iterator_exhausted:
                # Call _get_page_data for a page far ahead to trigger fetching.
                # The internal logic of _get_page_data handles appending to _async_buffer.
                # We just need to ensure it continues until StopAsyncIteration.
                # A more direct way to exhaust:
                if hasattr(self.data_source, '__anext__'):
                    try:
                        # Keep fetching one by one and adding to buffer
                        # This loop ensures that _get_page_data's internal exhaustion logic is triggered.
                        # This is slightly inefficient as _get_page_data might re-iterate parts of the buffer.
                        # A dedicated _fetch_all method in the view would be cleaner.
                        # For now, rely on _get_page_data to buffer everything when a high page number is requested.
                         await self._get_page_data( (len(self._async_buffer) // self.items_per_page) + 10 ) # Try to fetch a few pages ahead
                         if not self._async_buffer: # Break if nothing was fetched, means iterator was empty from start
                             break

                    except StopAsyncIteration: # Should be handled by _get_page_data
                        self._async_iterator_exhausted = True # Ensure it's set
                        break
                else: # Not an async iterator as expected
                    self._async_iterator_exhausted = True
                    break

            # After attempting to fetch all, total_pages should be set.
            if self.total_pages is None: # If still None, means iterator was empty or error
                self.total_pages = math.ceil(len(self._async_buffer) / self.items_per_page) if len(self._async_buffer) > 0 else 1


        if self.total_pages is not None and self.current_page_number < self.total_pages - 1:
            self.current_page_number = self.total_pages - 1
            # If we deferred, we need to use followup or edit the original response
            if deferred and interaction.response.is_done(): # Check is_done again, defer might complete fast
                 await self._update_view_internals()
                 await interaction.followup.send(content=self.current_page_content, embed=self.current_page_embed, view=self)
                 # We probably want to delete the original "thinking" message if possible, or edit it.
                 # If original_response exists, try editing.
                 try: # Edit the original deferred message
                    await interaction.edit_original_response(content=self.current_page_content, embed=self.current_page_embed, view=self)
                 except discord.NotFound: # Original response might not be editable or found
                    pass # Fallback to followup already done or handle as error
                 return # Return after handling deferred response

            # If not deferred or response not done, proceed with normal navigation
            if not interaction.response.is_done():
                 await self._navigate(interaction)
            else: # Response was done but not by our defer (e.g. by previous button click very fast)
                 await self._update_view_internals() # Update content/embed
                 await interaction.edit_original_response(content=self.current_page_content, embed=self.current_page_embed, view=self)

        else: # Already on last page or total_pages still somehow unknown
            if not interaction.response.is_done():
                await interaction.response.defer()
            # else: the interaction is already handled or timed out

    async def stop_pagination(self, interaction: discord.Interaction):
        self.stop() # Stop the view (inherited from discord.ui.View)
        # EnhancedView's on_timeout (which stop() might call or similar logic) should disable components.
        # We can also explicitly disable them here.
        # Ensure all buttons are disabled.
        if self.show_page_buttons:
            buttons_to_disable = [
                self.first_page_button, self.prev_page_button,
                self.next_page_button, self.last_page_button, self.stop_button
            ]
            for button in buttons_to_disable:
                if button: # Check if button exists
                    button.disabled = True

        # Respond to the interaction that initiated the stop
        # Using edit_message on the original message to show the disabled state.
        try:
            await interaction.response.edit_message(
                content=self.current_page_content, # Keep current content
                embed=self.current_page_embed,   # Keep current embed
                view=self                        # Pass the view with disabled components
            )
        except discord.InteractionResponded: # If already responded (e.g. by a quick timeout)
            if self.message: # Try to edit the message directly if interaction already responded
                try:
                    await self.message.edit(view=self)
                except discord.HTTPException:
                    pass # Ignore if message edit fails (e.g. deleted)
        except discord.HTTPException:
            pass # Ignore other HTTP exceptions during stop


    async def send_initial_message(self, interaction_or_ctx: Union[discord.Interaction, discord.abc.Messageable]) -> discord.Message:
        """
        Sends the first page of the paginator.
        Can be called with an Interaction (for slash commands) or a Context/Channel (for message commands).
        """
        await self._update_view_internals() # Format the first page

        if isinstance(interaction_or_ctx, discord.Interaction):
            if not interaction_or_ctx.response.is_done():
                await interaction_or_ctx.response.send_message(
                    content=self.current_page_content,
                    embed=self.current_page_embed,
                    view=self
                )
                self.message = await interaction_or_ctx.original_response()
            else: # Interaction already responded to (e.g., deferred)
                self.message = await interaction_or_ctx.followup.send(
                    content=self.current_page_content,
                    embed=self.current_page_embed,
                    view=self,
                    wait=True
                )
        elif hasattr(interaction_or_ctx, 'send'): # Covers Context, TextChannel, etc.
            self.message = await interaction_or_ctx.send( # type: ignore
                content=self.current_page_content,
                embed=self.current_page_embed,
                view=self
            )
        else:
            raise TypeError("interaction_or_ctx must be discord.Interaction or a messageable object.")

        return self.message

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.author_id:
            if interaction.user.id != self.author_id:
                await interaction.response.send_message("You are not allowed to interact with this.", ephemeral=True)
                return False
        return True

    async def on_timeout(self) -> None:
        # EnhancedView's on_timeout (which super().on_timeout() calls) should disable components.
        # We just need to ensure it's called.
        # If further custom action on timeout is needed for AdvancedPaginatorView, add it here.
        # For example, logging the timeout.
        # print(f"Paginator for message {self.message.id if self.message else 'Unknown'} timed out.")
        if self.message and not self.is_finished(): # is_finished might be set by super().on_timeout
             # If EnhancedView didn't edit the message to reflect disabled state, do it here.
             # However, EnhancedView.on_timeout is expected to handle this.
             # This is more of a failsafe or if specific content change is needed.
            pass # Relying on EnhancedView to disable components and edit message.
        await super().on_timeout()


# Example usage (conceptual, for testing within this file if needed)
async def main_test():
    # This requires a running bot and context to actually send messages.
    # For now, this is a structural placeholder.

    # Test with a list
    list_data = [f"Item {i}" for i in range(25)]
    # paginator_list = AdvancedPaginatorView(data_source=list_data, items_per_page=5)
    # page_0_list = await paginator_list._get_page_data(0)
    # print(f"List - Page 0: {page_0_list}") # Expected: Item 0-4
    # page_4_list = await paginator_list._get_page_data(4)
    # print(f"List - Page 4: {page_4_list}") # Expected: Item 20-24
    # print(f"List - Total Pages: {paginator_list.total_pages}") # Expected: 5

    # Test with an async iterator
    async def async_gen():
        for i in range(13):
            await asyncio.sleep(0.01) # Simulate async work
            yield f"Async Item {i}"

    # paginator_async = AdvancedPaginatorView(data_source=async_gen(), items_per_page=3)
    # page_0_async = await paginator_async._get_page_data(0)
    # print(f"Async - Page 0: {page_0_async}") # Expected: Async Item 0-2
    # page_1_async = await paginator_async._get_page_data(1)
    # print(f"Async - Page 1: {page_1_async}") # Expected: Async Item 3-5
    # page_4_async = await paginator_async._get_page_data(4) # This will fetch till the end
    # print(f"Async - Page 4: {page_4_async}") # Expected: Async Item 12 (one item)
    # print(f"Async - Total Pages (after fetching page 4): {paginator_async.total_pages}") # Expected: 5

if __name__ == "__main__":
    import asyncio
    # To run main_test, you'd typically do:
    # asyncio.run(main_test())
    # However, this test is more for verifying the _get_page_data logic locally.
    # Full testing requires bot integration.
    pass
