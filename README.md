# Databricks Agent Template

This is a template repository for creating Databricks agent applications. Use this template to create customer-specific implementations.

## Quick Start

1. Click "Use this template" to create a new repository
2. Clone your new repository
3. Install dependencies: `pip install -r requirements.txt`
4. Configure your Databricks settings
5. Run the application: `streamlit run app.py`

## Project Structure

```
├── app.py                 # Main Streamlit application
├── app.yaml              # Databricks app configuration
├── messages.py           # Message handling utilities
├── model_serving_utils.py # Model serving utilities
├── requirements.txt      # Python dependencies
└── README.md            # This file
```

## Configuration

Update the following files for your specific implementation:
- `app.yaml`: Configure Databricks app settings
- `app.py`: Customize the application logic
- `messages.py`: Modify message handling as needed

## Customer-Specific Development

This template provides a foundation for Databricks agent applications. Customize the following areas for each customer:

1. **App Configuration** (`app.yaml`)
2. **UI/UX Customization** (`app.py`)
3. **Message Processing** (`messages.py`)
4. **Model Integration** (`model_serving_utils.py`)

## Support

For questions or issues, please refer to the Databricks documentation or contact the development team.
