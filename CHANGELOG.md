# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - YYYY-MM-DD
### Added
- **Advanced Pagination (`AdvancedPaginatorView`)**:
    - Supports synchronous lists and asynchronous iterators as data sources.
    - Handles multiple content types:
        - `embeds`: Paginates a list of `discord.Embed` objects.
        - `text_lines`: Paginates a list of strings, displaying them as lines in an embed.
        - `generic`: Allows custom formatting of any item list via a `formatter_func`.
    - Navigation controls:
        - Standard buttons: First, Previous, Next, Last, Stop. (Labelled Page indicator button)
        - Optional "Jump to Page" button that opens a modal for direct page number input.
        - Optional page selection dropdown menu (dynamically generates options based on total pages).
    - `EnhancedContext.paginate()` helper method for easy creation and sending of paginated messages.
- **Form Creation/Processing Helper (`DispyplusForm`)**:
    - Declarative definition of form fields using `text_field()` (currently for `discord.ui.TextInput`).
    - Automatic construction of modals from defined fields.
    - Built-in support for:
        - Required fields.
        - Target type conversion (e.g., to `int`, `bool`). Boolean conversion handles 'yes'/'no', 'true'/'false', '1'/'0'.
        - Custom validation functions per field (can return boolean or tuple with error message).
    - `EnhancedContext.ask_form()` helper method to display a form and await its processed data or `None` (on timeout/validation failure).
    - `BaseFormField` and `TextInputFormField` classes for structured field definition and future extensibility to other component types.
- **Unit Tests**:
    - Added comprehensive unit tests for `AdvancedPaginatorView` (`tests/ui/test_pagination.py`).
    - Added comprehensive unit tests for `DispyplusForm` (`tests/ui/test_forms.py`).
- **Examples**:
    - New `example/pagination_example.py` demonstrating various use cases of `AdvancedPaginatorView`.
    - Updated `example/ui_example.py` with a more detailed example of `DispyplusForm` usage via `ctx.ask_form()`, including type conversion and validation.

### Changed
- Renamed `FormField` to `BaseFormField` and introduced `TextInputFormField` for clarity and future extensibility.
- Renamed `field()` helper to `text_field()` to specify it's for text inputs.
- `DispyplusForm` now uses an `asyncio.Future` internally to allow `EnhancedContext.ask_form` to await results.
- `DispyplusForm.on_submit` now handles type conversion and validation, then calls `process_form_data` with processed data. Validation errors are reported to the user via an ephemeral message.
- Updated `setup.py` and `dispyplus/__init__.py` with new version `0.2.0`.
- Added new UI components to `dispyplus.ui.__all__`.

### Deprecated
- (None in this version)

### Removed
- (None in this version)

### Fixed
- (No specific bug fixes noted for this version as it's primarily feature additions)

### Security
- (No security vulnerabilities addressed in this version)

## [0.1.2] - Previous Version
### Changed
- Refactoring and internal improvements. (Details would be in previous changelog entries if they existed)

## [0.1.1] and earlier
- Initial releases and foundational features. (Details would be in previous changelog entries)
