# Customer Setup Guide

This guide helps you set up a new customer-specific Databricks agent application.

## Prerequisites

- Python 3.8+
- Databricks workspace access
- Git

## Setup Steps

### 1. Create Repository from Template

1. Go to the [template repository](https://github.com/ankity09/databricks-agent-template)
2. Click "Use this template"
3. Name your repository: `databricks-agent-{customer-name}`
4. Set visibility (Private recommended for customer work)
5. Click "Create repository from template"

### 2. Clone and Setup

```bash
git clone https://github.com/ankity09/databricks-agent-{customer-name}.git
cd databricks-agent-{customer-name}
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure for Customer

#### Update `app.yaml`
```yaml
command: [
  "streamlit", 
  "run",
  "app.py"
]

env:
  - name: STREAMLIT_BROWSER_GATHER_USAGE_STATS
    value: "false"
  - name: "SERVING_ENDPOINT"
    valueFrom: "serving-endpoint"
  # Add customer-specific environment variables here
```

#### Update `app.py`
- Modify the title and branding
- Add customer-specific logic
- Update the UI components as needed

#### Update `messages.py`
- Customize message handling for customer requirements
- Add customer-specific validation rules

### 5. Test Locally

```bash
streamlit run app.py
```

### 6. Deploy to Databricks

Follow your organization's deployment process for Databricks applications.

## Customer-Specific Customizations

### Common Areas to Customize:

1. **Branding & UI**
   - App title and description
   - Color scheme
   - Logo and images

2. **Functionality**
   - Message processing logic
   - Model integration
   - Data handling

3. **Configuration**
   - Environment variables
   - Databricks settings
   - External service integrations

4. **Documentation**
   - Update README.md with customer-specific information
   - Add customer-specific setup instructions

## Best Practices

- Keep customer-specific code well-documented
- Use environment variables for sensitive configuration
- Test thoroughly before deployment
- Maintain a clear separation between template code and customer customizations
- Regular updates from the base template (when applicable)

## Support

For questions about this template or customer implementations, contact the development team.
