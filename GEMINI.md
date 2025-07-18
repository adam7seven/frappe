# Gemini AI Rules for This Project

## Project Overview

1. This project is forked from Frappe[https://github.com/frappe/frappe]
2. A critical modification has been made to the core Frappe Framework: the primary key for all DocTypes has been changed from `name` (string) to `id` (integer/autoincrement/string). All AI-generated or modified code must respect this fundamental change. Queries, controller logic, and client-side scripts should use `id` as the unique identifier for records.

## Technology Stack

- **Backend:** Python, Frappe Framework
- **Frontend:** JavaScript, HTML, CSS (including standard Frappe UI components)
- **Database:** PostgreSQL

## Important Commands

- **Start Development Server:** To run the development server, use the standard command:
  ```bash
  bench start
  ```
- **Run Tests:** Tests are run using the standard Frappe command. Remember to specify the site.
  ```bash
  bench --site [your-site-name] run-tests
  ```

## Coding Standards

Please adhere to the general coding standards and best practices of the Frappe developer community. This includes following Python's PEP 8 guidelines and the established JavaScript style used throughout the Frappe and ERPNext codebases.
