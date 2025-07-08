import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List, Tuple, Any # Added Any

import discord

# Assuming dispyplus structure, adjust imports as necessary
from dispyplus.ui.pagination import PaginatorView
from dispyplus.ui.components import JumpToPageModal # Moved JumpToPageModal
from dispyplus.core.context import EnhancedContext # For testing the helper

# Minimal mock for discord.ui.View.stop for EnhancedView inheritance
class MockEnhancedView(discord.ui.View):
    def __init__(self, timeout: float = 180.0):
        super().__init__(timeout=timeout)
        self.message = None

    async def on_timeout(self):
        pass # Simplified for testing

    def stop(self): # Ensure stop is present
        super().stop()


@pytest.fixture
def mock_interaction():
    interaction = AsyncMock(spec=discord.Interaction)
    interaction.response = AsyncMock(spec=discord.InteractionResponse)
    interaction.followup = AsyncMock(spec=discord.Webhook)
    interaction.user = AsyncMock(spec=discord.User)
    interaction.user.id = 12345
    interaction.message = None # Can be set per test if needed
    interaction.response.is_done.return_value = False
    return interaction

@pytest.fixture
def mock_context(mock_interaction): # Depends on mock_interaction for author
    ctx = AsyncMock(spec=EnhancedContext)
    ctx.author = mock_interaction.user # Link author for author_id checks
    ctx.interaction = None # Default to message command context for some tests
    ctx.send = AsyncMock(return_value=AsyncMock(spec=discord.Message)) # Mock ctx.send

    # Mock parts of the bot if EnhancedContext tries to access them (e.g., bot.logger)
    ctx.bot = MagicMock()
    ctx.bot.logger = MagicMock(spec=discord.client.Client.logger) # More specific if possible
    return ctx


# --- Data Source Fixtures ---
@pytest.fixture
def sync_list_data():
    return [f"Item {i}" for i in range(50)] # 50 items

@pytest.fixture
async def async_iterator_data():
    async def generator():
        for i in range(30): # 30 items
            # await asyncio.sleep(0.001) # Simulate async work if needed for timing tests
            yield f"Async Item {i}"
    return generator()

# --- Test PaginatorView ---

@pytest.mark.asyncio
async def test_paginator_init_sync(sync_list_data):
    view = PaginatorView(data_source=sync_list_data, items_per_page=10)
    assert view.items_per_page == 10
    assert view.total_pages == 5 # 50 items / 10 per page
    assert not view._is_async_iterator
    assert view.current_page_number == 0

@pytest.mark.asyncio
async def test_paginator_init_async(async_iterator_data):
    view = PaginatorView(data_source=async_iterator_data, items_per_page=7)
    assert view.items_per_page == 7
    assert view.total_pages is None # Not known until data is fetched
    assert view._is_async_iterator
    assert view.current_page_number == 0

@pytest.mark.asyncio
async def test_get_page_data_sync(sync_list_data):
    view = PaginatorView(data_source=sync_list_data, items_per_page=10)
    page_0 = await view._get_page_data(0)
    assert len(page_0) == 10
    assert page_0[0] == "Item 0"
    page_4 = await view._get_page_data(4)
    assert len(page_4) == 10
    assert page_4[-1] == "Item 49"
    page_5 = await view._get_page_data(5) # Out of bounds
    assert len(page_5) == 0

@pytest.mark.asyncio
async def test_get_page_data_async(async_iterator_data):
    view = PaginatorView(data_source=async_iterator_data, items_per_page=7)
    page_0 = await view._get_page_data(0) # Fetches first 7
    assert len(page_0) == 7
    assert page_0[0] == "Async Item 0"
    assert len(view._async_buffer) == 7

    page_1 = await view._get_page_data(1) # Fetches next 7 (total 14 in buffer)
    assert len(page_1) == 7
    assert page_1[0] == "Async Item 7"
    assert len(view._async_buffer) == 14

    # Fetch all pages to exhaust iterator
    # 30 items / 7 per page = 4.28 -> 5 pages
    # Page 0: 0-6
    # Page 1: 7-13
    # Page 2: 14-20
    # Page 3: 21-27
    # Page 4: 28-29 (2 items)
    page_4 = await view._get_page_data(4)
    assert len(page_4) == 2 # 30 items total, last page has 2
    assert page_4[-1] == "Async Item 29"
    assert view._async_iterator_exhausted
    assert view.total_pages == 5

    page_5 = await view._get_page_data(5) # Out of bounds
    assert len(page_5) == 0


@pytest.mark.asyncio
async def test_format_page_default_generic(sync_list_data):
    view = PaginatorView(data_source=sync_list_data, items_per_page=3, content_type="generic")
    view.current_page_number = 0
    content, embed = await view.format_page()
    assert content is None
    assert isinstance(embed, discord.Embed)
    assert "Page 1/17" in embed.title # 50 items / 3 per page = 16.6 -> 17 pages
    assert "Item 0" in embed.description
    assert "Item 1" in embed.description
    assert "Item 2" in embed.description
    assert "Item 3" not in embed.description

@pytest.mark.asyncio
async def test_format_page_text_lines(sync_list_data):
    view = PaginatorView(data_source=sync_list_data, items_per_page=2, content_type="text_lines")
    view.current_page_number = 1 # Page 2
    # Items on page 2 (0-indexed page 1) are "Item 2", "Item 3"
    content, embed = await view.format_page()
    assert content is None
    assert isinstance(embed, discord.Embed)
    assert "Page 2/25" in embed.title
    assert embed.description == "Item 2\nItem 3"

@pytest.mark.asyncio
async def test_format_page_embeds():
    embed_list = [discord.Embed(title=f"Embed {i}") for i in range(3)]
    view = PaginatorView(data_source=embed_list, items_per_page=1, content_type="embeds")
    view.current_page_number = 1
    content, embed = await view.format_page()
    assert content is None
    assert isinstance(embed, discord.Embed)
    assert embed.title == "Embed 1"
    assert "Page 2/3" in embed.footer.text

def custom_formatter(items: List[str], page_num: int, view_instance: PaginatorView) -> Tuple[str, discord.Embed]:
    content_str = f"Custom Content for Page {page_num + 1}"
    embed_ = discord.Embed(title=f"Custom Formatted Page {page_num + 1}", description="\n".join(items))
    return content_str, embed_

@pytest.mark.asyncio
async def test_format_page_custom_formatter(sync_list_data):
    view = PaginatorView(
        data_source=sync_list_data,
        items_per_page=5,
        content_type="generic",
        formatter_func=custom_formatter
    )
    view.current_page_number = 0
    content, embed = await view.format_page()
    assert content == "Custom Content for Page 1"
    assert isinstance(embed, discord.Embed)
    assert embed.title == "Custom Formatted Page 1"
    assert "Item 0" in embed.description
    assert "Item 4" in embed.description


# Mocking send_initial_message and button callbacks requires more involved setup
# For button callbacks, we need to simulate an interaction and check message edits.

@pytest.mark.asyncio
async def test_button_states_initial(sync_list_data):
    view = PaginatorView(data_source=sync_list_data, items_per_page=10, show_page_buttons=True)
    await view._update_button_states() # Call manually as send_initial_message is not called

    assert view.first_page_button.disabled is True
    assert view.prev_page_button.disabled is True
    assert view.next_page_button.disabled is False
    assert view.last_page_button.disabled is False
    assert view.current_page_label_button.label == "Page 1/5"

@pytest.mark.asyncio
async def test_button_states_last_page(sync_list_data):
    view = PaginatorView(data_source=sync_list_data, items_per_page=10, show_page_buttons=True)
    view.current_page_number = 4 # Last page (0-indexed)
    await view._update_button_states()

    assert view.first_page_button.disabled is False
    assert view.prev_page_button.disabled is False
    assert view.next_page_button.disabled is True
    assert view.last_page_button.disabled is True
    assert view.current_page_label_button.label == "Page 5/5"

@pytest.mark.asyncio
async def test_navigation_next_prev(sync_list_data, mock_interaction):
    # This test is more complex as it involves UI interaction and message editing
    # We'll simplify by checking current_page_number and assuming _navigate works
    view = PaginatorView(data_source=sync_list_data, items_per_page=10, show_page_buttons=True)
    view.message = AsyncMock(spec=discord.Message) # Mock the message attribute

    # Patch _navigate to prevent actual discord calls and check its call
    with patch.object(view, '_navigate', new_callable=AsyncMock) as mock_navigate:
        # Go to Next Page
        await view.go_to_next_page(mock_interaction)
        assert view.current_page_number == 1
        mock_navigate.assert_called_once_with(mock_interaction)
        mock_navigate.reset_mock()

        # Go to Previous Page
        await view.go_to_previous_page(mock_interaction)
        assert view.current_page_number == 0
        mock_navigate.assert_called_once_with(mock_interaction)

@pytest.mark.asyncio
async def test_stop_pagination(sync_list_data, mock_interaction):
    view = PaginatorView(data_source=sync_list_data, items_per_page=10, show_page_buttons=True)
    view.message = AsyncMock(spec=discord.Message) # Mock the message attribute
    view.current_page_content = "Test" # Set some content for edit_message
    view.current_page_embed = None

    # Mock edit_message for the interaction
    mock_interaction.response.edit_message = AsyncMock()

    # Call stop_pagination
    await view.stop_pagination(mock_interaction)

    # Assert view is stopped and buttons are disabled
    assert view.is_finished() is True # discord.ui.View.is_finished()
    assert view.first_page_button.disabled is True
    assert view.next_page_button.disabled is True # All nav buttons should be disabled

    # Assert edit_message was called on the interaction to update the view
    mock_interaction.response.edit_message.assert_called_once_with(
        content="Test", embed=None, view=view
    )

# --- Test JumpToPageModal ---
@pytest.mark.asyncio
async def test_jump_to_page_modal_submit_valid(mock_interaction):
    # Mock the paginator view that the modal would interact with
    mock_paginator_view = AsyncMock(spec=PaginatorView)
    mock_paginator_view.total_pages = 10
    mock_paginator_view._navigate = AsyncMock() # Mock the navigation method

    modal = JumpToPageModal(paginator_view=mock_paginator_view)
    modal.page_number_input.value = "5" # User inputs "5"

    await modal.on_submit(mock_interaction)

    assert mock_paginator_view.current_page_number == 4 # 0-indexed
    mock_paginator_view._navigate.assert_called_once_with(mock_interaction)

@pytest.mark.asyncio
async def test_jump_to_page_modal_submit_invalid_oor(mock_interaction): # Out Of Range
    mock_paginator_view = AsyncMock(spec=PaginatorView)
    mock_paginator_view.total_pages = 5

    modal = JumpToPageModal(paginator_view=mock_paginator_view)
    modal.page_number_input.value = "10" # Invalid page

    await modal.on_submit(mock_interaction)

    mock_interaction.response.send_message.assert_called_once()
    args, kwargs = mock_interaction.response.send_message.call_args
    assert "Invalid page number" in args[0]
    assert kwargs.get("ephemeral") is True
    assert mock_paginator_view.current_page_number != 9 # Should not change

@pytest.mark.asyncio
async def test_jump_to_page_modal_submit_invalid_nan(mock_interaction): # Not A Number
    mock_paginator_view = AsyncMock(spec=PaginatorView)
    mock_paginator_view.total_pages = 5

    modal = JumpToPageModal(paginator_view=mock_paginator_view)
    modal.page_number_input.value = "abc" # Invalid input

    await modal.on_submit(mock_interaction)

    mock_interaction.response.send_message.assert_called_once()
    args, kwargs = mock_interaction.response.send_message.call_args
    assert "Invalid input" in args[0]
    assert kwargs.get("ephemeral") is True

# --- Test EnhancedContext.paginate helper ---
@pytest.mark.asyncio
async def test_enhanced_context_paginate_helper(mock_context, sync_list_data):
    # Patch PaginatorView to check its instantiation and method calls
    with patch('dispyplus.core.context.PaginatorView', autospec=True) as MockPaginator:
        mock_paginator_instance = MockPaginator.return_value
        mock_paginator_instance.send_initial_message = AsyncMock(return_value=AsyncMock(spec=discord.Message))

        # Call the helper
        message = await mock_context.paginate(data_source=sync_list_data, items_per_page=5)

        # Assert PaginatorView was called correctly
        MockPaginator.assert_called_once_with(
            data_source=sync_list_data,
            items_per_page=5,
            formatter_func=None, # Default
            content_type="generic", # Default
            show_page_buttons=True, # Default
            timeout=180.0, # Default
            author_id=mock_context.author.id
        )

        # Assert send_initial_message was called on the instance
        mock_paginator_instance.send_initial_message.assert_called_once_with(mock_context)

        # Assert a message object was returned
        assert isinstance(message, discord.Message)


@pytest.mark.asyncio
async def test_page_select_menu_update_and_callback(sync_list_data, mock_interaction):
    view = PaginatorView(
        data_source=sync_list_data,
        items_per_page=10,
        show_page_select=True,
        show_page_buttons=False # Simplify by not having other buttons for this test focus
    )
    view.message = AsyncMock(spec=discord.Message)

    # Initial state (total_pages should be 5)
    await view._update_button_states() # This updates the select menu options

    assert view.page_select_menu is not None
    assert view.page_select_menu.disabled is False
    assert len(view.page_select_menu.options) == 5 # 50 items / 10 per page = 5 pages
    assert view.page_select_menu.options[0].label == "Page 1"
    assert view.page_select_menu.options[0].value == "0"
    assert view.page_select_menu.options[0].default is True # Current page 0

    # Simulate selecting page 3 (value "2") from the select menu
    view.page_select_menu.values = ["2"] # Mock the selection

    with patch.object(view, '_navigate', new_callable=AsyncMock) as mock_navigate:
        await view.select_page_from_menu(mock_interaction)
        assert view.current_page_number == 2
        mock_navigate.assert_called_once_with(mock_interaction)
        mock_navigate.reset_mock()

    # Check if select options default value updated
    await view._update_button_states()
    assert view.page_select_menu.options[2].default is True
    assert view.page_select_menu.options[0].default is False


# Placeholder for more tests:
# - Test with show_jump_button=True and its interaction
# - Test various combinations of show_ flags for buttons/select/jump
# - Test formatter_func error handling
# - Test async iterator exhaustion during _get_page_data and its effect on total_pages and button states
# - Test interaction_check with author_id
# - Test on_timeout behavior (inherited from EnhancedView but ensure components are disabled)

# Note: Testing the visual layout of buttons (rows) is hard in unit tests.
# That's better for manual/integration testing.
# This test suite focuses on logic and state changes.
