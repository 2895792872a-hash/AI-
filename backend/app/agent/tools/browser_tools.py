"""Browser tool definitions in Anthropic's tool-use format.

These tools are presented to Claude so it can call browser operations
as structured tool invocations rather than generating raw code.
"""

BROWSER_TOOLS: list[dict] = [
    {
        "name": "browser_navigate",
        "description": "Navigate the browser to a specified URL. Always use this first if a website is involved.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Full URL to navigate to, e.g. https://www.example.com",
                }
            },
            "required": ["url"],
        },
    },
    {
        "name": "browser_click",
        "description": "Click on an element identified by a CSS selector. Wait for the element to be visible first.",
        "input_schema": {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS selector of the element to click, e.g. button.submit or #search-btn",
                }
            },
            "required": ["selector"],
        },
    },
    {
        "name": "browser_type",
        "description": "Type text into an input field (clears existing content first).",
        "input_schema": {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS selector of the input field",
                },
                "text": {
                    "type": "string",
                    "description": "Text to type into the field",
                },
            },
            "required": ["selector", "text"],
        },
    },
    {
        "name": "browser_scroll",
        "description": "Scroll the page up or down by a number of pixels.",
        "input_schema": {
            "type": "object",
            "properties": {
                "direction": {
                    "type": "string",
                    "enum": ["up", "down"],
                    "description": "Direction to scroll",
                },
                "amount": {
                    "type": "integer",
                    "description": "Pixels to scroll (default 500)",
                },
            },
            "required": ["direction"],
        },
    },
    {
        "name": "browser_extract",
        "description": "Extract text content from the current page or a specific element. Use after navigating to the right page.",
        "input_schema": {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "Optional CSS selector. Omit to extract the full page text.",
                }
            },
            "required": [],
        },
    },
    {
        "name": "browser_screenshot",
        "description": "Take a screenshot of the current page.",
        "input_schema": {
            "type": "object",
            "properties": {
                "full_page": {
                    "type": "boolean",
                    "description": "Capture the full scrollable page (default: visible viewport only)",
                }
            },
            "required": [],
        },
    },
    {
        "name": "task_complete",
        "description": "Signal that all browser operations are finished. Call this when the task is done and you have the information needed.",
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "What was accomplished and what information was gathered",
                },
                "data": {
                    "type": "object",
                    "description": "Any structured data collected during the task (prices, names, URLs, etc.)",
                },
            },
            "required": ["summary"],
        },
    },
]
