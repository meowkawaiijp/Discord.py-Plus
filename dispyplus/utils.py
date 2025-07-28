"""
Utility functions for Discord bot development.
"""

import asyncio
from typing import Any, Optional, Union
from datetime import datetime, timezone
import discord
from discord.ext import commands


def get_user_avatar(user: Union[discord.User, discord.Member], size: int = 1024) -> str:
    """
    Get a user's avatar URL with fallback to default avatar.
    
    Args:
        user: The Discord user or member
        size: The desired avatar size (must be power of 2)
        
    Returns:
        The avatar URL as a string
    """
    if user.avatar:
        return user.avatar.with_size(size).url
    else:
        return user.default_avatar.url


def format_timestamp(
    dt: datetime, 
    style: str = "f"
) -> str:
    """
    Format a datetime object as a Discord timestamp.
    
    Args:
        dt: The datetime object to format
        style: Discord timestamp style:
            - 't': Short Time (16:20)
            - 'T': Long Time (16:20:30)
            - 'd': Short Date (20/04/2021)
            - 'D': Long Date (20 April 2021)
            - 'f': Short Date/Time (20 April 2021 16:20)
            - 'F': Long Date/Time (Tuesday, 20 April 2021 16:20)
            - 'R': Relative Time (2 months ago)
            
    Returns:
        Formatted Discord timestamp string
    """
    # Ensure timezone awareness
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    timestamp = int(dt.timestamp())
    return f"<t:{timestamp}:{style}>"


async def safe_send(
    destination: Union[discord.TextChannel, discord.User, discord.Member, discord.Interaction],
    content: str = None,
    *,
    embed: discord.Embed = None,
    file: discord.File = None,
    files: list = None,
    view: discord.ui.View = None,
    ephemeral: bool = False,
    fallback_dm: bool = True,
    **kwargs
) -> Optional[discord.Message]:
    """
    Safely send a message with error handling and fallback options.
    
    Args:
        destination: Where to send the message
        content: Message content
        embed: Message embed
        file: Single file to attach
        files: Multiple files to attach
        view: UI view to attach
        ephemeral: Whether the message should be ephemeral (for interactions)
        fallback_dm: Whether to try DMing the user if channel send fails
        **kwargs: Additional keyword arguments for send()
        
    Returns:
        The sent message or None if failed
    """
    send_kwargs = {
        "content": content,
        "embed": embed,
        "file": file,
        "files": files,
        "view": view,
        **kwargs
    }
    
    # Remove None values
    send_kwargs = {k: v for k, v in send_kwargs.items() if v is not None}
    
    try:
        # Handle different destination types
        if isinstance(destination, discord.Interaction):
            if destination.response.is_done():
                return await destination.followup.send(ephemeral=ephemeral, **send_kwargs)
            else:
                await destination.response.send_message(ephemeral=ephemeral, **send_kwargs)
                return await destination.original_response()
        
        elif hasattr(destination, 'send'):
            return await destination.send(**send_kwargs)
        
        else:
            raise ValueError(f"Invalid destination type: {type(destination)}")
    
    except discord.Forbidden:
        # Try to DM the user if it's a member/user and fallback is enabled
        if fallback_dm and isinstance(destination, (discord.Member, discord.User)):
            try:
                return await destination.send(**send_kwargs)
            except discord.Forbidden:
                pass
        
        # If it's an interaction with a member, try DMing them
        elif fallback_dm and isinstance(destination, discord.Interaction) and destination.user:
            try:
                return await destination.user.send(**send_kwargs)
            except discord.Forbidden:
                pass
    
    except discord.HTTPException as e:
        print(f"HTTP error while sending message: {e}")
    
    except Exception as e:
        print(f"Unexpected error while sending message: {e}")
    
    return None


def create_embed(
    title: str = None,
    description: str = None,
    *,
    color: Union[discord.Color, int] = None,
    author: Union[discord.User, discord.Member] = None,
    thumbnail: str = None,
    image: str = None,
    footer: str = None,
    timestamp: datetime = None,
    fields: list = None
) -> discord.Embed:
    """
    Create a Discord embed with common options.
    
    Args:
        title: Embed title
        description: Embed description
        color: Embed color
        author: User to set as author (uses their avatar and name)
        thumbnail: Thumbnail URL
        image: Image URL
        footer: Footer text
        timestamp: Timestamp for the embed
        fields: List of field dictionaries with 'name', 'value', and optional 'inline'
        
    Returns:
        Configured Discord embed
    """
    embed = discord.Embed(
        title=title,
        description=description,
        color=color or discord.Color.blue(),
        timestamp=timestamp
    )
    
    if author:
        embed.set_author(
            name=author.display_name,
            icon_url=get_user_avatar(author)
        )
    
    if thumbnail:
        embed.set_thumbnail(url=thumbnail)
    
    if image:
        embed.set_image(url=image)
    
    if footer:
        embed.set_footer(text=footer)
    
    if fields:
        for field in fields:
            embed.add_field(
                name=field.get('name', 'Field'),
                value=field.get('value', 'Value'),
                inline=field.get('inline', True)
            )
    
    return embed


def chunk_text(text: str, max_length: int = 2000) -> list:
    """
    Split text into chunks that fit within Discord's message limits.
    
    Args:
        text: The text to split
        max_length: Maximum length per chunk
        
    Returns:
        List of text chunks
    """
    if len(text) <= max_length:
        return [text]
    
    chunks = []
    current_chunk = ""
    
    for line in text.split('\n'):
        if len(current_chunk) + len(line) + 1 <= max_length:
            if current_chunk:
                current_chunk += '\n' + line
            else:
                current_chunk = line
        else:
            if current_chunk:
                chunks.append(current_chunk)
            
            # If a single line is too long, split it by words
            if len(line) > max_length:
                words = line.split(' ')
                current_chunk = ""
                
                for word in words:
                    if len(current_chunk) + len(word) + 1 <= max_length:
                        if current_chunk:
                            current_chunk += ' ' + word
                        else:
                            current_chunk = word
                    else:
                        if current_chunk:
                            chunks.append(current_chunk)
                        current_chunk = word
            else:
                current_chunk = line
    
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks


def humanize_duration(seconds: int) -> str:
    """
    Convert seconds to a human-readable duration string.
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Human-readable duration string
    """
    if seconds < 60:
        return f"{seconds}s"
    
    minutes = seconds // 60
    if minutes < 60:
        remaining_seconds = seconds % 60
        if remaining_seconds == 0:
            return f"{minutes}m"
        return f"{minutes}m {remaining_seconds}s"
    
    hours = minutes // 60
    remaining_minutes = minutes % 60
    
    if hours < 24:
        if remaining_minutes == 0:
            return f"{hours}h"
        return f"{hours}h {remaining_minutes}m"
    
    days = hours // 24
    remaining_hours = hours % 24
    
    if remaining_hours == 0:
        return f"{days}d"
    return f"{days}d {remaining_hours}h"


def parse_duration(duration_str: str) -> Optional[int]:
    """
    Parse a duration string into seconds.
    
    Supports formats like: 1h30m, 2d, 45s, 1h 30m 15s
    
    Args:
        duration_str: Duration string to parse
        
    Returns:
        Duration in seconds or None if invalid
    """
    import re
    
    # Remove spaces and convert to lowercase
    duration_str = duration_str.replace(' ', '').lower()
    
    # Pattern to match duration components
    pattern = r'(\d+)([dhms])'
    matches = re.findall(pattern, duration_str)
    
    if not matches:
        return None
    
    total_seconds = 0
    multipliers = {
        's': 1,
        'm': 60,
        'h': 3600,
        'd': 86400
    }
    
    for value, unit in matches:
        if unit in multipliers:
            total_seconds += int(value) * multipliers[unit]
        else:
            return None
    
    return total_seconds


async def wait_for_reaction(
    message: discord.Message,
    user: Union[discord.User, discord.Member],
    emojis: list,
    timeout: float = 60.0
) -> Optional[str]:
    """
    Wait for a user to react with one of the specified emojis.
    
    Args:
        message: The message to wait for reactions on
        user: The user whose reaction to wait for
        emojis: List of emoji strings to wait for
        timeout: Timeout in seconds
        
    Returns:
        The emoji that was reacted with, or None if timeout
    """
    # Add the emojis to the message
    for emoji in emojis:
        try:
            await message.add_reaction(emoji)
        except discord.HTTPException:
            pass
    
    def check(reaction, reaction_user):
        return (
            reaction_user == user and
            str(reaction.emoji) in emojis and
            reaction.message.id == message.id
        )
    
    try:
        reaction, _ = await message.bot.wait_for('reaction_add', check=check, timeout=timeout)
        return str(reaction.emoji)
    except asyncio.TimeoutError:
        return None


def is_url(text: str) -> bool:
    """
    Check if a string is a valid URL.
    
    Args:
        text: String to check
        
    Returns:
        True if the string is a URL, False otherwise
    """
    import re
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    
    return url_pattern.match(text) is not None


def escape_markdown(text: str) -> str:
    """
    Escape Discord markdown characters in text.
    
    Args:
        text: Text to escape
        
    Returns:
        Text with markdown characters escaped
    """
    markdown_chars = ['*', '_', '`', '~', '|', '\\']
    
    for char in markdown_chars:
        text = text.replace(char, '\\' + char)
    
    return text


def limit_string(text: str, max_length: int, suffix: str = "...") -> str:
    """
    Limit a string to a maximum length, adding a suffix if truncated.
    
    Args:
        text: Text to limit
        max_length: Maximum length
        suffix: Suffix to add if truncated
        
    Returns:
        Limited string
    """
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix