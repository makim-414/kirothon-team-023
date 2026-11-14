# Requirements Document

## Introduction

Rollcall (package `album-mcp`) is an MCP (Model Context Protocol) server that connects the macOS Photos app library to AI assistants (Kiro, Claude). It enables users to capture screenshots and automatically organize them into events, insights, and references through AI classification. The system performs OCR on captures, stores metadata locally, creates calendar events from date-containing captures, and provides natural language search with visual preview selection.

## Glossary

- **Album_MCP_Server**: The Python FastMCP server that provides tools for photo library access and classification
- **Photos_Library**: The macOS Photos app library containing user photos and screenshots
- **Capture**: A screenshot or photo stored in the Photos_Library
- **Classification_DB**: The local SQLite database storing capture metadata, OCR results, classifications, and tags
- **AI_Assistant**: The external AI system (Kiro or Claude) that calls MCP tools to classify and search captures
- **Event_Capture**: A Capture classified as containing date/time information requiring calendar entry
- **Album_Calendar**: The dedicated calendar named "Rollcall" for storing events from captures
- **OCR_Text**: Extracted text from a Capture in Korean or English
- **Apple_Label**: Apple's built-in image recognition label (e.g., "Car", "Screenshot", "Document")
- **Preview_Grid**: A numbered composite image showing multiple capture thumbnails for AI visual selection
- **Capture_Kind**: Classification category: event, insight, reference, or other

## Requirements

### Requirement 1: Screenshot Synchronization

**User Story:** As a user, I want new screenshots automatically discovered from my Photos library, so that I don't have to manually select which captures to process.

#### Acceptance Criteria

1. WHEN the AI_Assistant calls sync_captures with a timestamp, THE Album_MCP_Server SHALL return all Captures created after that timestamp
2. THE Album_MCP_Server SHALL filter results to include only screenshots and exclude other photo types
3. THE Album_MCP_Server SHALL return capture metadata including id, creation date, and file path
4. WHEN a Capture's original file is stored only in iCloud, THE Album_MCP_Server SHALL use the local preview instead of downloading the original
5. FOR ALL returned Captures, the creation date SHALL be accurate within 1 second of the Photos_Library timestamp

### Requirement 2: Unprocessed Capture Queue

**User Story:** As an AI assistant, I want to retrieve a batch of unprocessed captures, so that I can classify them efficiently.

#### Acceptance Criteria

1. WHEN the AI_Assistant calls inbox with count n, THE Album_MCP_Server SHALL return up to n Captures that have not been classified
2. THE Album_MCP_Server SHALL order unprocessed Captures by creation date ascending
3. WHEN fewer than n unprocessed Captures exist, THE Album_MCP_Server SHALL return all available unprocessed Captures
4. THE Album_MCP_Server SHALL include OCR_Text and Apple_Label for each returned Capture

### Requirement 3: OCR Text Extraction

**User Story:** As a user, I want text automatically extracted from my screenshots, so that I can search by content later.

#### Acceptance Criteria

1. WHEN a new Capture is synchronized, THE Album_MCP_Server SHALL extract OCR_Text in Korean and English
2. THE Album_MCP_Server SHALL store the OCR_Text in the Classification_DB linked to the Capture id
3. WHEN OCR extraction fails, THE Album_MCP_Server SHALL store an empty string and log the error
4. THE Album_MCP_Server SHALL preserve text layout information including line breaks and spacing
5. FOR ALL Captures with visible text, OCR accuracy SHALL exceed 90% for clearly rendered characters

### Requirement 4: Apple Label Extraction

**User Story:** As a user, I want Apple's image recognition labels stored with my captures, so that I can search by visual content.

#### Acceptance Criteria

1. WHEN a new Capture is synchronized, THE Album_MCP_Server SHALL retrieve all Apple_Label values from the Photos_Library
2. THE Album_MCP_Server SHALL store Apple_Label values in the Classification_DB linked to the Capture id
3. WHEN no Apple_Label exists for a Capture, THE Album_MCP_Server SHALL store an empty list
4. THE Album_MCP_Server SHALL preserve all Apple_Label values without modification

### Requirement 5: Capture Classification

**User Story:** As an AI assistant, I want to classify captures with kind, summary, and tags, so that they can be retrieved later.

#### Acceptance Criteria

1. WHEN the AI_Assistant calls file_capture with id, kind, summary, and tags, THE Album_MCP_Server SHALL store the classification in the Classification_DB
2. THE Album_MCP_Server SHALL validate that kind is one of: "event", "insight", "reference", or "other"
3. THE Album_MCP_Server SHALL reject classifications where summary exceeds 200 characters
4. THE Album_MCP_Server SHALL store tags as a list of strings in the Classification_DB
5. WHEN a Capture is classified twice, THE Album_MCP_Server SHALL update the existing classification record

### Requirement 6: Calendar Event Creation

**User Story:** As a user, I want captures containing dates automatically added to my calendar, so that I don't miss important events.

#### Acceptance Criteria

1. WHEN the AI_Assistant calls add_event with capture_id, title, start, end, and place, THE Album_MCP_Server SHALL create an event in the Album_Calendar
2. THE Album_MCP_Server SHALL store the capture_id in the event's notes field
3. THE Album_MCP_Server SHALL validate that start time is before or equal to end time
4. WHEN place is provided, THE Album_MCP_Server SHALL set the event location field
5. WHEN the Album_Calendar does not exist, THE Album_MCP_Server SHALL create it before adding the event
6. THE Album_MCP_Server SHALL return the created event's calendar id

### Requirement 7: Natural Language Search

**User Story:** As a user, I want to search my captures using natural language, so that I can find captures without remembering exact keywords.

#### Acceptance Criteria

1. WHEN the AI_Assistant calls search with query, kind, and period, THE Album_MCP_Server SHALL return matching Captures ranked by relevance
2. THE Album_MCP_Server SHALL search across summary, tags, OCR_Text, and Apple_Label fields
3. WHEN kind is specified, THE Album_MCP_Server SHALL filter results to that Capture_Kind
4. WHEN period is specified, THE Album_MCP_Server SHALL filter results to Captures created within that date range
5. THE Album_MCP_Server SHALL return up to 50 results ordered by relevance score descending
6. FOR ALL search queries, response time SHALL be under 2 seconds

### Requirement 8: Visual Preview Generation

**User Story:** As an AI assistant, I want to see a numbered grid of capture thumbnails, so that I can visually select the correct capture.

#### Acceptance Criteria

1. WHEN the AI_Assistant calls look_at with a list of ids, THE Album_MCP_Server SHALL generate a Preview_Grid containing all specified Captures
2. THE Album_MCP_Server SHALL overlay each thumbnail with its position number (1, 2, 3, ...)
3. THE Album_MCP_Server SHALL arrange thumbnails in a grid layout with maximum 4 columns
4. THE Album_MCP_Server SHALL resize each thumbnail to 400x400 pixels maximum while preserving aspect ratio
5. THE Album_MCP_Server SHALL return the Preview_Grid as a base64-encoded image
6. WHEN any specified id does not exist, THE Album_MCP_Server SHALL skip that id and include only valid Captures

### Requirement 9: Single Photo Retrieval

**User Story:** As an AI assistant, I want to retrieve a full-resolution photo by id, so that I can show it to the user or analyze details.

#### Acceptance Criteria

1. WHEN the AI_Assistant calls get_photo with an id, THE Album_MCP_Server SHALL return the Capture as a base64-encoded image
2. THE Album_MCP_Server SHALL include metadata: creation date, dimensions, file size, OCR_Text, Apple_Label, and classification
3. WHEN the original file is stored only in iCloud, THE Album_MCP_Server SHALL use the highest-resolution local preview
4. WHEN the id does not exist, THE Album_MCP_Server SHALL return an error message
5. THE Album_MCP_Server SHALL return images in JPEG format with 90% quality

### Requirement 10: Batch Photo Export

**User Story:** As a user, I want to export multiple captures to a folder, so that I can share them or process them externally.

#### Acceptance Criteria

1. WHEN the AI_Assistant calls export_photos with ids and folder, THE Album_MCP_Server SHALL copy all specified Captures to the folder
2. THE Album_MCP_Server SHALL name exported files using the pattern: {original_name}_{capture_id}.{extension}
3. WHEN the folder does not exist, THE Album_MCP_Server SHALL create it
4. WHEN any id does not exist, THE Album_MCP_Server SHALL skip that id and export only valid Captures
5. THE Album_MCP_Server SHALL return a list of successfully exported file paths

### Requirement 11: Local-Only Data Storage

**User Story:** As a user, I want all photo data to remain on my Mac, so that my privacy is protected.

#### Acceptance Criteria

1. THE Album_MCP_Server SHALL store all metadata in a local Classification_DB file
2. THE Album_MCP_Server SHALL access Photos_Library files only via local file system paths
3. THE Album_MCP_Server SHALL process all images locally without network requests
4. THE Album_MCP_Server SHALL reject any configuration that would transmit photo data to external services

### Requirement 12: Read-Only Photo Library Access

**User Story:** As a user, I want the Photos library to remain unmodified, so that the MCP server cannot corrupt my photo collection.

#### Acceptance Criteria

1. THE Album_MCP_Server SHALL open Photos_Library in read-only mode
2. THE Album_MCP_Server SHALL reject any operation that would modify Photos_Library metadata
3. THE Album_MCP_Server SHALL reject any operation that would delete or move photos in the Photos_Library
4. WHEN osxphotos attempts a write operation, THE Album_MCP_Server SHALL raise an error before execution

### Requirement 13: Database Schema Management

**User Story:** As a developer, I want the database schema automatically created and migrated, so that I don't have to manually manage database structure.

#### Acceptance Criteria

1. WHEN the Album_MCP_Server starts and the Classification_DB does not exist, THE Album_MCP_Server SHALL create it with the current schema
2. THE Album_MCP_Server SHALL store schema version in the Classification_DB
3. WHEN the Classification_DB schema version is older than the code version, THE Album_MCP_Server SHALL apply migrations automatically
4. THE Album_MCP_Server SHALL log all schema changes to the console
5. WHEN a migration fails, THE Album_MCP_Server SHALL restore the previous database state from backup

### Requirement 14: Error Handling and Logging

**User Story:** As a developer, I want detailed error messages and logs, so that I can diagnose issues quickly.

#### Acceptance Criteria

1. WHEN any MCP tool encounters an error, THE Album_MCP_Server SHALL return a structured error response with error type and message
2. THE Album_MCP_Server SHALL log all tool invocations with parameters to the console at INFO level
3. THE Album_MCP_Server SHALL log all errors with stack traces to the console at ERROR level
4. WHEN Photos_Library access fails, THE Album_MCP_Server SHALL return an error message indicating permission issues
5. THE Album_MCP_Server SHALL include request id in all log messages for tracing

### Requirement 15: MCP Server Configuration

**User Story:** As a user, I want to configure the MCP server in Kiro and Claude, so that I can use it with my AI assistant.

#### Acceptance Criteria

1. THE project SHALL include an mcp.json file with server configuration for Kiro
2. THE project SHALL include a Claude configuration example showing server setup
3. THE project SHALL include a README with installation and configuration instructions
4. THE configuration files SHALL specify the Python interpreter path and server entry point
5. THE configuration files SHALL specify required environment variables if any

### Requirement 16: Steering Document

**User Story:** As an AI assistant, I want guidance on how to use Album MCP tools in sequence, so that I can process captures effectively.

#### Acceptance Criteria

1. THE project SHALL include a steering document describing the three core workflows
2. THE steering document SHALL specify the tool call sequence for the accumulation workflow
3. THE steering document SHALL specify the tool call sequence for the event creation workflow
4. THE steering document SHALL specify the tool call sequence for the retrieval workflow
5. THE steering document SHALL include example queries and expected tool usage patterns

### Requirement 17: Automated Capture Processing

**User Story:** As a user, I want new captures automatically processed on a schedule, so that my capture inbox stays current.

#### Acceptance Criteria

1. THE project SHALL include a Kiro hook that triggers periodic capture processing
2. THE hook SHALL call sync_captures to find new captures since last run
3. THE hook SHALL call inbox to retrieve unprocessed captures
4. THE hook SHALL invoke the AI_Assistant to classify each unprocessed capture
5. THE hook SHALL run on a configurable schedule (default: every 30 minutes)
6. WHEN the hook fails, THE hook SHALL log the error and retry on the next scheduled run
### Requirement 18: Multiple Capture Sources
**User Story:** As a user who also uses an Android phone or keeps screenshots outside Photos, I want to index image folders too, so that all my captures are searchable in one place.
#### Acceptance Criteria
1. THE Album_MCP_Server SHALL support a `photos` source (macOS Photos_Library via osxphotos) and a `folder` source (any local directory of images)
2. THE folder source SHALL accept multiple directories via the `ALBUM_MCP_FOLDERS` environment variable (colon-separated)
3. THE folder source SHALL treat png, jpg, jpeg, heic, and webp files as Captures and use file modification time as creation date
4. THE README SHALL document how to sync Android screenshots into a folder (Google Drive for desktop, `adb pull`, or USB)
5. WHEN the photos source cannot open the Photos_Library because of missing Full Disk Access, THE Album_MCP_Server SHALL return an error explaining how to grant it and SHALL keep the folder source working
6. Capture ids SHALL be prefixed by source (`photos:<uuid>`, `folder:<sha1>`) so ids never collide across sources
### Requirement 19: Multiple Calendar Backends
**User Story:** As a user, I want events created in the calendar I actually use, whether that is Apple Calendar, Google Calendar, or something else.
#### Acceptance Criteria
1. THE Album_MCP_Server SHALL support `apple` (macOS Calendar via AppleScript), `google` (Google Calendar API), and `ics` (.ics file opened by the default calendar app) backends, selected with `ALBUM_MCP_CALENDAR`
2. THE `google` backend SHALL use OAuth credentials stored outside the repository and SHALL never log tokens
3. THE `ics` backend SHALL write a valid RFC 5545 file to a local folder and return its path
4. THE Album_MCP_Server SHALL record every created event (backend, event id, capture id) in the Classification_DB so the same capture is not added twice
