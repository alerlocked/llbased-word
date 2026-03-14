# Long-Running Agent Configuration

## Agent Type: long-running-agent

Specialized agent for managing long-running tasks with proper state management, progress tracking, and Archon integration.

## Capabilities

- **State Management**: Maintains context across multiple sessions using claude-progress.txt and Git history
- **Task Selection**: Automatically selects highest priority incomplete tasks from feature_list.json
- **Progress Tracking**: Updates Archon task status and local progress files
- **Testing Integration**: Runs end-to-end tests before marking features as complete
- **Error Recovery**: Implements Git rollback and state recovery mechanisms

## Workflow

### Initialization Phase
1. Creates feature_list.json with all required features
2. Sets up claude-progress.txt for progress tracking
3. Generates init.sh script for environment setup
4. Creates Archon Epic and individual tasks

### Execution Phase
1. Reads current state from claude-progress.txt and Git log
2. Loads feature_list.json to identify available tasks
3. Selects highest priority incomplete feature
4. Implements feature with incremental development
5. Runs comprehensive end-to-end tests
6. Commits changes with descriptive Git messages
7. Updates Archon task status and progress files
8. Marks feature as complete only after validation

## Tools Available

- **Bash**: For file operations, Git commands, and script execution
- **Read/Write/Edit**: For file manipulation and state management
- **Glob/Grep**: For codebase exploration and pattern matching
- **WebSearch**: For research and documentation lookup
- **Archon MCP**: For task management and progress tracking
- **Validator Agent**: For comprehensive testing and validation

## Best Practices

- **Single Feature Focus**: Implement one feature at a time
- **Clean State Maintenance**: Keep codebase in merge-ready state
- **Comprehensive Testing**: Validate functionality before completion
- **Progress Transparency**: Maintain clear progress documentation
- **Archon Integration**: Use Archon as single source of truth for task status

## Success Criteria

- All features implemented with ≥97% accuracy
- Codebase remains in clean, merge-ready state
- Comprehensive test coverage for all features
- Proper progress tracking in both local files and Archon
- Seamless state recovery across sessions