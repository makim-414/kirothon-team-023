# Requirements Document

## Introduction

Rollcall (package `album-mcp`) is an MCP (Model Context Protocol) server that connects the macOS Photos app library to AI assistants (Kiro, Claude). It enables users to capture screenshots and automatically organize them into events, insights, and references through AI classification. The system performs OCR on captures, stores metadata locally, creates calendar events from date-containing captures, and provides natural language search with visual preview selection.

## Glossary

- **Album_MCP_Server**: The Python FastMCP server that provides tools for photo library access and classification. The Album_MCP_Server contains no LLM; all classification decisions are made by the AI_Assistant
- **Photos_Library**: The macOS Photos app library containing user photos and screenshots
- **Capture**: A screenshot or photo stored in the Photos_Library
- **Screenshot**: A Capture that osxphotos flags as a screenshot
- **General_Photo**: A Capture in the Photos_Library that is not a Screenshot
- **Classification_DB**: The local SQLite database storing capture metadata, OCR results, classifications, tags, and the last successful sync time
- **AI_Assistant**: The external AI system (Kiro or Claude) that calls MCP tools to classify and search captures
- **MCP_Client**: The local process (Kiro or Claude Desktop) that launches the Album_MCP_Server and communicates with the Album_MCP_Server over stdio
- **Event_Capture**: A Capture classified as containing date/time information requiring calendar entry
- **Album_Calendar**: The dedicated macOS Calendar calendar named "앨범 MCP" for storing events from captures
- **OCR_Text**: Extracted text from a Capture in Korean or English
- **Apple_Label**: Apple's built-in image recognition label (e.g., "Car", "Screenshot", "Document")
- **Preview_Grid**: A numbered composite image showing multiple capture thumbnails for AI visual selection
- **Capture_Kind**: Classification category: event, insight, reference, or other
- **Local_Preview**: The derivative image that the Photos_Library stores on the Mac when the original file is stored only in iCloud
- **Steering_Document**: The Kiro steering markdown file that instructs the AI_Assistant how to use the Album_MCP_Server tools
- **Capture_Hook**: The Kiro agent hook named "새 캡처 정리" stored in `.kiro/hooks/`
- **Indexing_CLI**: The command-line entry point of the Album_MCP_Server that runs OCR and Apple_Label indexing without AI classification

## Requirements

### Requirement 1: Screenshot Synchronization

**User Story:** As a user, I want new screenshots automatically discovered from my Photos library, so that I don't have to manually select which captures to process.

#### Acceptance Criteria

1. WHEN the AI_Assistant calls sync_captures with an ISO 8601 `since` timestamp, THE Album_MCP_Server SHALL find up to 1000 Screenshots created after the `since` timestamp and, for each Screenshot not yet stored, extract OCR_Text and Apple_Label and store the OCR_Text and Apple_Label in the Classification_DB
2. IF the `since` value is malformed or later than the current time, THEN THE Album_MCP_Server SHALL return an error indicating an invalid timestamp
3. THE Album_MCP_Server SHALL identify Screenshots using the osxphotos screenshot flag and exclude other media from capture synchronization
4. WHEN sync_captures completes, THE Album_MCP_Server SHALL return for each synchronized Screenshot the id, the creation date in ISO 8601 format, and whether a local original or only a Local_Preview was available
5. WHEN the original file of a Screenshot exists only in iCloud, THE Album_MCP_Server SHALL use the Local_Preview and SHALL NOT download the original
6. WHEN no new Screenshots exist after the `since` timestamp, THE Album_MCP_Server SHALL return an empty result without an error
7. WHEN sync_captures is run again over an already synchronized period, THE Album_MCP_Server SHALL keep exactly one capture record per Screenshot in the Classification_DB
8. WHEN the AI_Assistant calls sync_captures without a `since` value, THE Album_MCP_Server SHALL use the last successful sync time stored in the Classification_DB

### Requirement 2: Unprocessed Capture Queue

**User Story:** As an AI assistant, I want to retrieve a batch of unprocessed captures, so that I can classify them efficiently.

#### Acceptance Criteria

1. WHEN the AI_Assistant calls inbox with count n, THE Album_MCP_Server SHALL return up to n Captures that have not been classified, ordered by creation date ascending
2. WHEN the AI_Assistant calls inbox without a count, THE Album_MCP_Server SHALL use a count of 20
3. IF n is less than 1 or greater than 100, THEN THE Album_MCP_Server SHALL return an error indicating an invalid count
4. WHEN inbox returns a Capture, THE Album_MCP_Server SHALL include the OCR_Text of the Capture, using an empty string when no OCR_Text exists
5. WHEN inbox returns a Capture, THE Album_MCP_Server SHALL include the Apple_Label list of the Capture, using an empty list when no Apple_Label exists
6. WHEN fewer than n unclassified Captures exist, THE Album_MCP_Server SHALL return all unclassified Captures

### Requirement 3: OCR Text Extraction

**User Story:** As a user, I want text automatically extracted from my screenshots, so that I can search by content later.

#### Acceptance Criteria

1. WHEN a new Screenshot is synchronized, THE Album_MCP_Server SHALL extract OCR_Text in Korean and English using on-device macOS Vision text recognition
2. WHEN OCR_Text is extracted, THE Album_MCP_Server SHALL store the OCR_Text in the Classification_DB linked to the Capture id
3. WHEN OCR_Text is extracted, THE Album_MCP_Server SHALL preserve the line breaks of the recognized text
4. IF OCR extraction fails or exceeds 30 seconds for a Capture, THEN THE Album_MCP_Server SHALL store an empty string as the OCR_Text, log the failure, and continue processing the remaining Captures

### Requirement 4: Apple Label Extraction

**User Story:** As a user, I want Apple's image recognition labels stored with my captures, so that I can search by visual content.

#### Acceptance Criteria

1. WHEN a new Screenshot is synchronized, THE Album_MCP_Server SHALL store the Apple_Label values in the Classification_DB exactly as osxphotos returns the Apple_Label values, linked to the Capture id
2. WHEN no Apple_Label exists for a Capture, THE Album_MCP_Server SHALL store an empty list
3. IF Apple_Label retrieval fails for a Capture, THEN THE Album_MCP_Server SHALL store an empty list and continue processing the remaining Captures

### Requirement 5: Capture Classification

**User Story:** As an AI assistant, I want to classify captures with kind, summary, and tags, so that they can be retrieved later.

#### Acceptance Criteria

1. WHEN the AI_Assistant calls file_capture with a valid id, kind, summary, and tags, THE Album_MCP_Server SHALL store the classification in the Classification_DB and return a confirmation
2. IF kind is not one of "event", "insight", "reference", or "other", THEN THE Album_MCP_Server SHALL return an error indicating an invalid kind
3. IF summary exceeds 200 characters, THEN THE Album_MCP_Server SHALL return an error indicating the summary is too long
4. IF tags contains more than 20 entries or any tag exceeds 50 characters, THEN THE Album_MCP_Server SHALL return an error indicating invalid tags
5. IF the id does not match a Capture in the Classification_DB, THEN THE Album_MCP_Server SHALL return an error indicating the Capture was not found
6. IF id, kind, or summary is empty, THEN THE Album_MCP_Server SHALL return an error indicating invalid input
7. WHEN a Capture that is already classified is classified again, THE Album_MCP_Server SHALL replace the existing classification with the new classification
8. IF storing the classification fails, THEN THE Album_MCP_Server SHALL leave the existing classification data of the Capture unchanged and return an error

### Requirement 6: Calendar Event Creation

**User Story:** As a user, I want captures containing dates automatically added to my calendar, so that I don't miss important events.

#### Acceptance Criteria

1. WHEN the AI_Assistant calls add_event with capture_id, title, an ISO 8601 start, and an optional ISO 8601 end and place, THE Album_MCP_Server SHALL create an event in the Album_Calendar and return the created event id
2. IF capture_id or title is empty, THEN THE Album_MCP_Server SHALL return an error indicating invalid input
3. IF start or end is not a valid ISO 8601 date-time, THEN THE Album_MCP_Server SHALL return an error indicating an invalid date-time
4. IF start is later than end, THEN THE Album_MCP_Server SHALL return an error indicating an invalid time range
5. WHEN end is omitted, THE Album_MCP_Server SHALL set the event end to one hour after start
6. WHEN place is provided, THE Album_MCP_Server SHALL set the event location to the place value
7. WHEN an event is created, THE Album_MCP_Server SHALL write the capture_id into the event notes
8. WHEN the Album_Calendar does not exist, THE Album_MCP_Server SHALL create the Album_Calendar before adding the event
9. IF Calendar access is denied or the Album_Calendar cannot be created, THEN THE Album_MCP_Server SHALL return an error explaining how to grant Calendar permission in macOS privacy settings
10. THE Album_MCP_Server SHALL write events only to the Album_Calendar and SHALL NOT modify other calendars

### Requirement 7: Natural Language Search

**User Story:** As a user, I want to search my captures using natural language, so that I can find captures without remembering exact keywords.

#### Acceptance Criteria

1. WHEN the AI_Assistant calls search with a query, THE Album_MCP_Server SHALL search all Captures in the Photos_Library, including Screenshots and General_Photos
2. WHEN search evaluates a Screenshot, THE Album_MCP_Server SHALL match the query against summary, tags, OCR_Text, and Apple_Label
3. WHEN search evaluates a General_Photo, THE Album_MCP_Server SHALL match the query against Apple_Label, date, and place metadata from osxphotos
4. THE Album_MCP_Server SHALL match query terms by case-insensitive substring comparison
5. THE Album_MCP_Server SHALL score each match with field weights of 4 for summary, 3 for tags, 2 for OCR_Text, and 1 for Apple_Label
6. WHEN kind is specified, THE Album_MCP_Server SHALL return only classified Captures of that Capture_Kind
7. WHEN period is specified as an ISO 8601 start and end, THE Album_MCP_Server SHALL return only Captures created within that period
8. THE Album_MCP_Server SHALL return up to 50 results ordered by score descending, then by creation date descending
9. WHEN search returns a result, THE Album_MCP_Server SHALL include the id, creation date, kind (null when unclassified), summary (null when absent), and matched fields
10. WHILE the Photos_Library contains up to 50,000 photos, THE Album_MCP_Server SHALL complete each search within 2 seconds
11. WHEN query is empty and kind or period is specified, THE Album_MCP_Server SHALL return Captures matching the filters, so that label-only and period-only searches can widen candidates for visual confirmation
12. IF query is empty and neither kind nor period is specified, THEN THE Album_MCP_Server SHALL return an error indicating invalid input
13. WHEN no Captures match, THE Album_MCP_Server SHALL return an empty list
14. IF kind or period is invalid, THEN THE Album_MCP_Server SHALL return an error indicating the invalid parameter

### Requirement 8: Visual Preview Generation

**User Story:** As an AI assistant, I want to see a numbered grid of capture thumbnails, so that I can visually select the correct capture.

#### Acceptance Criteria

1. WHEN the AI_Assistant calls look_at with a list of ids, THE Album_MCP_Server SHALL generate a Preview_Grid from the first 50 ids and ignore any additional ids
2. WHEN a Preview_Grid is generated, THE Album_MCP_Server SHALL overlay each thumbnail with a number from 1 to N in the order of the given ids
3. THE Album_MCP_Server SHALL arrange Preview_Grid thumbnails in at most 4 columns
4. THE Album_MCP_Server SHALL resize each thumbnail so the long edge is at most 400 pixels while preserving aspect ratio
5. WHEN a Preview_Grid is generated, THE Album_MCP_Server SHALL return the Preview_Grid as MCP PNG image content together with the mapping from each number to its Capture id
6. WHEN an id does not match a Capture, THE Album_MCP_Server SHALL skip that id and include only valid Captures
7. IF none of the given ids match a Capture, THEN THE Album_MCP_Server SHALL return an error indicating no valid Captures
8. WHEN the original file of a Capture exists only in iCloud, THE Album_MCP_Server SHALL use the Local_Preview for the thumbnail

### Requirement 9: Single Photo Retrieval

**User Story:** As an AI assistant, I want to retrieve a full-resolution photo by id, so that I can show it to the user or analyze details.

#### Acceptance Criteria

1. WHEN the AI_Assistant calls get_photo with an id, THE Album_MCP_Server SHALL return the Capture as MCP JPEG image content at quality 90 with the long edge capped at 2048 pixels
2. WHEN get_photo returns a Capture, THE Album_MCP_Server SHALL include creation_date, dimensions, file_size, OCR_Text, Apple_Label, and classification, using null for absent values
3. WHEN the original file exists only in iCloud, THE Album_MCP_Server SHALL use the largest available Local_Preview
4. IF the id does not match a Capture, THEN THE Album_MCP_Server SHALL return a not found error
5. IF the image file of the Capture cannot be read, THEN THE Album_MCP_Server SHALL return an unavailable error
6. IF the id is empty, THEN THE Album_MCP_Server SHALL return an invalid input error

### Requirement 10: Batch Photo Export

**User Story:** As a user, I want to export multiple captures to a folder, so that I can share them or process them externally.

#### Acceptance Criteria

1. WHEN the AI_Assistant calls export_photos with ids and a local folder path, THE Album_MCP_Server SHALL copy each matching Capture to the folder and return the exported file paths and the skipped ids
2. IF ids is empty or contains more than 100 entries, THEN THE Album_MCP_Server SHALL return an error indicating an invalid id list
3. IF the folder is not a local file system path, THEN THE Album_MCP_Server SHALL return an error indicating an invalid folder
4. WHEN the folder does not exist, THE Album_MCP_Server SHALL create the folder including missing parent folders
5. IF the folder cannot be created or written because of a permission failure, THEN THE Album_MCP_Server SHALL return an error indicating the permission failure
6. THE Album_MCP_Server SHALL name each exported file `{original_name}_{capture_id}.{ext}`
7. IF a file with the target name already exists, THEN THE Album_MCP_Server SHALL append a numeric suffix to the new file name and SHALL NOT overwrite the existing file
8. WHEN an id does not match a Capture, THE Album_MCP_Server SHALL skip that id and list the id as skipped
9. WHEN the original file of a Capture exists only in iCloud, THE Album_MCP_Server SHALL export the Local_Preview and mark the exported entry as a preview in the result
10. THE Album_MCP_Server SHALL export by copying files and SHALL NOT modify the Photos_Library

### Requirement 11: Local-Only Data Storage

**User Story:** As a user, I want all photo data to remain on my Mac, so that my privacy is protected.

#### Acceptance Criteria

1. THE Album_MCP_Server SHALL store the Classification_DB as a local SQLite file in `~/Library/Application Support/album-mcp/` by default
2. WHERE the Classification_DB path environment variable is set, THE Album_MCP_Server SHALL store the Classification_DB at the path given by the environment variable
3. THE Album_MCP_Server SHALL NOT make outbound network requests
4. THE Album_MCP_Server SHALL produce OCR_Text, Apple_Label data, and thumbnails on-device
5. THE Album_MCP_Server SHALL return image data only to the calling MCP_Client over local stdio

### Requirement 12: Read-Only Photo Library Access

**User Story:** As a user, I want the Photos library to remain unmodified, so that the MCP server cannot corrupt my photo collection.

#### Acceptance Criteria

1. THE Album_MCP_Server SHALL open the Photos_Library in read-only mode through osxphotos
2. THE Album_MCP_Server SHALL NOT expose any MCP tool that modifies, adds, deletes, or moves photos, albums, or Photos_Library metadata
3. THE Album_MCP_Server SHALL store classifications only in the Classification_DB

### Requirement 13: Database Schema Management

**User Story:** As a developer, I want the database schema automatically created and migrated, so that I don't have to manually manage database structure.

#### Acceptance Criteria

1. WHEN the Album_MCP_Server starts and the Classification_DB does not exist, THE Album_MCP_Server SHALL create the Classification_DB with the current schema and store the schema version
2. WHEN the Album_MCP_Server starts and the stored schema version is older than the code schema version, THE Album_MCP_Server SHALL apply all pending migrations in a single transaction
3. IF a migration fails, THEN THE Album_MCP_Server SHALL roll back the transaction, log the failure, and exit with a non-zero status

### Requirement 14: Error Handling and Logging

**User Story:** As a developer, I want detailed error messages and logs, so that I can diagnose issues quickly.

#### Acceptance Criteria

1. WHEN any MCP tool encounters an error, THE Album_MCP_Server SHALL return a structured error containing `error_type` and `message`
2. WHEN an MCP tool call completes, THE Album_MCP_Server SHALL log the tool name and duration to stderr, keeping stdout reserved for MCP stdio
3. THE Album_MCP_Server SHALL NOT write OCR_Text or image data to logs
4. IF Photos_Library or Calendar access fails because of missing permission, THEN THE Album_MCP_Server SHALL return an error naming the macOS privacy setting to grant

### Requirement 15: MCP Server Configuration

**User Story:** As a user, I want to configure the MCP server in Kiro and Claude, so that I can use it with my AI assistant.

#### Acceptance Criteria

1. THE project SHALL include a Kiro `.kiro/settings/mcp.json` file defining the Album_MCP_Server with `command`, `args`, and `env`
2. THE project SHALL include a Claude Desktop `claude_desktop_config.json` example defining the Album_MCP_Server with the same `command`, `args`, and `env` fields
3. THE project configuration files SHALL launch the Album_MCP_Server using either the absolute path to the project virtual environment Python or `uv run`
4. THE README SHALL document installation, required macOS permissions, configuration file locations, and how to verify the MCP_Client connection

### Requirement 16: Steering Document

**User Story:** As an AI assistant, I want guidance on how to use Album MCP tools in sequence, so that I can process captures effectively.

#### Acceptance Criteria

1. THE Steering_Document SHALL describe the accumulation, event, and retrieval workflows, each with purpose, inputs, outputs, tool call order, and data flow
2. THE Steering_Document SHALL specify failure handling for each tool as retry, skip, or abort
3. THE Steering_Document SHALL include at least one example query for each workflow
4. THE Steering_Document SHALL state the two-step retrieval rule: use search to narrow candidates, then use look_at to confirm visually before calling get_photo or answering
5. THE Steering_Document SHALL state that the AI_Assistant decides the kind, summary, tags, and events of each Capture
6. THE Steering_Document SHALL instruct the AI_Assistant to call add_event only when a Capture contains an explicit date, resolving relative dates against the Capture creation date

### Requirement 17: Automated Capture Processing

**User Story:** As a user, I want new captures automatically processed, so that my capture inbox stays current.

#### Acceptance Criteria

1. THE project SHALL include the Capture_Hook as a Kiro agent hook in `.kiro/hooks/`
2. WHEN a Kiro session starts, THE Capture_Hook SHALL instruct the AI_Assistant to call sync_captures, then inbox, then file_capture for each returned Capture, then add_event for each Event_Capture with an explicit date
3. WHEN the user triggers the Capture_Hook manually, THE Capture_Hook SHALL run the same processing sequence as at session start
4. WHEN the Capture_Hook calls sync_captures, THE Capture_Hook SHALL omit `since` so that the Album_MCP_Server uses the last successful sync time (Requirement 1.8)
5. WHILE the Capture_Hook is processing, THE Capture_Hook SHALL request at most 20 Captures per inbox call and repeat until inbox returns no Captures or 100 Captures have been processed
6. IF classification of a Capture fails, THEN THE Capture_Hook SHALL leave the Capture unclassified so that the Capture remains in the inbox for the next run
7. THE README SHALL document an optional launchd example that runs the Indexing_CLI at a fixed clock interval to perform OCR and Apple_Label indexing without AI classification

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
