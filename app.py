import logging
import os
import streamlit as st
from model_serving_utils import (
    endpoint_supports_feedback, 
    query_endpoint, 
    query_endpoint_stream, 
    _get_endpoint_task_type,
)
from collections import OrderedDict
from messages import UserMessage, AssistantResponse, render_message

# Page configuration
st.set_page_config(
    page_title="Pulse AI Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Customer configurations
CUSTOMER_CONFIGS = {
    "Fluke": {
        "logo_path": "customer_logos/Fluke_Corporation_logo.svg.png",
        "title": "Fluke Pulse AI Assistant",
        "subtitle": "Your intelligent companion for technical support and troubleshooting",
        "primary_color": "#FFD700",      # Yellow
        "primary_dark": "#FFC107",
        "secondary_color": "#0066CC",    # Blue
        "accent_color": "#000000",       # Black
        "chat_input_placeholder": "Ask about Fluke products, technical support, or troubleshooting..."
    },
    "Fortive": {
        "logo_path": "customer_logos/fortive_logo.jpeg",
        "title": "Fortive AI Assistant",
        "subtitle": "Intelligent solutions for industrial technology and professional instrumentation",
        "primary_color": "#00A3E0",      # Fortive Blue
        "primary_dark": "#0082B3",
        "secondary_color": "#003E51",    # Dark Blue
        "accent_color": "#002F3D",       # Darker Blue
        "chat_input_placeholder": "Ask about Fortive solutions, products, or services..."
    },
    "Informatica": {
        "logo_path": "customer_logos/informatica-logo.png",
        "title": "Informatica AI Assistant",
        "subtitle": "Your intelligent data management and integration companion",
        "primary_color": "#FF6B35",      # Informatica Orange
        "primary_dark": "#E85A2B",
        "secondary_color": "#2C3E50",    # Dark Gray-Blue
        "accent_color": "#1A252F",       # Very Dark Blue
        "chat_input_placeholder": "Ask about data integration, cloud solutions, or data governance..."
    },
    "Magic Eden": {
        "logo_path": "customer_logos/magic-eden.jpeg",
        "title": "Magic Eden AI Assistant",
        "subtitle": "Your NFT marketplace intelligent companion",
        "primary_color": "#E42575",      # Magic Eden Pink
        "primary_dark": "#C41E63",
        "secondary_color": "#7B61FF",    # Purple
        "accent_color": "#1F1F1F",       # Dark Gray
        "chat_input_placeholder": "Ask about NFTs, marketplace features, or trading..."
    }
}

# Load custom CSS with dynamic theming
def load_css(customer_config):
    with open('fluke_theme.css') as f:
        base_css = f.read()
    
    # Override CSS variables based on customer
    custom_css = f"""
    <style>
    {base_css}
    
    /* Customer-specific overrides */
    :root {{
        --fluke-yellow: {customer_config['primary_color']};
        --fluke-yellow-dark: {customer_config['primary_dark']};
        --fluke-blue: {customer_config['secondary_color']};
        --fluke-black: {customer_config['accent_color']};
    }}
    </style>
    """
    st.markdown(custom_css, unsafe_allow_html=True)

# Initialize session state for customer selection
if "selected_customer" not in st.session_state:
    st.session_state.selected_customer = "Fluke"

# Sidebar - Customer Selector
with st.sidebar:
    st.markdown("### 🏢 Customer Selection")
    selected_customer = st.selectbox(
        "Select Customer",
        options=list(CUSTOMER_CONFIGS.keys()),
        index=list(CUSTOMER_CONFIGS.keys()).index(st.session_state.selected_customer),
        key="customer_selector"
    )
    
    # Update session state if customer changed
    if selected_customer != st.session_state.selected_customer:
        st.session_state.selected_customer = selected_customer
        st.rerun()
    
    st.markdown("---")
    st.markdown("### ℹ️ About")
    st.markdown(f"Currently configured for **{selected_customer}**")
    st.markdown("Switch customers using the selector above to see different branding and themes.")

# Get current customer config
current_config = CUSTOMER_CONFIGS[st.session_state.selected_customer]

# Apply custom CSS with customer theme
load_css(current_config)

SERVING_ENDPOINT = os.getenv('SERVING_ENDPOINT')
assert SERVING_ENDPOINT, \
    ("Unable to determine serving endpoint to use for chatbot app. If developing locally, "
     "set the SERVING_ENDPOINT environment variable to the name of your serving endpoint. If "
     "deploying to a Databricks app, include a serving endpoint resource named "
     "'serving_endpoint' with CAN_QUERY permissions, as described in "
     "https://docs.databricks.com/aws/en/generative-ai/agent-framework/chat-app#deploy-the-databricks-app")

ENDPOINT_SUPPORTS_FEEDBACK = endpoint_supports_feedback(SERVING_ENDPOINT)

def reduce_chat_agent_chunks(chunks):
    """
    Reduce a list of ChatAgentChunk objects corresponding to a particular
    message into a single ChatAgentMessage
    """
    deltas = [chunk.delta for chunk in chunks]
    first_delta = deltas[0]
    result_msg = first_delta
    msg_contents = []
    
    # Accumulate tool calls properly
    tool_call_map = {}  # Map call_id to tool call for accumulation
    
    for delta in deltas:
        # Handle content
        if delta.content:
            msg_contents.append(delta.content)
            
        # Handle tool calls
        if hasattr(delta, 'tool_calls') and delta.tool_calls:
            for tool_call in delta.tool_calls:
                call_id = getattr(tool_call, 'id', None)
                tool_type = getattr(tool_call, 'type', "function")
                function_info = getattr(tool_call, 'function', None)
                if function_info:
                    func_name = getattr(function_info, 'name', "")
                    func_args = getattr(function_info, 'arguments', "")
                else:
                    func_name = ""
                    func_args = ""
                
                if call_id:
                    if call_id not in tool_call_map:
                        # New tool call
                        tool_call_map[call_id] = {
                            "id": call_id,
                            "type": tool_type,
                            "function": {
                                "name": func_name,
                                "arguments": func_args
                            }
                        }
                    else:
                        # Accumulate arguments for existing tool call
                        existing_args = tool_call_map[call_id]["function"]["arguments"]
                        tool_call_map[call_id]["function"]["arguments"] = existing_args + func_args

                        # Update function name if provided
                        if func_name:
                            tool_call_map[call_id]["function"]["name"] = func_name

        # Handle tool call IDs (for tool response messages)
        if hasattr(delta, 'tool_call_id') and delta.tool_call_id:
            result_msg = result_msg.model_copy(update={"tool_call_id": delta.tool_call_id})
    
    # Convert tool call map back to list
    if tool_call_map:
        accumulated_tool_calls = list(tool_call_map.values())
        result_msg = result_msg.model_copy(update={"tool_calls": accumulated_tool_calls})
    
    result_msg = result_msg.model_copy(update={"content": "".join(msg_contents)})
    return result_msg


def query_endpoint_and_render(task_type, input_messages):
    """Handle streaming response based on task type."""
    if task_type == "agent/v1/responses":
        return query_responses_endpoint_and_render(input_messages)
    elif task_type == "agent/v2/chat":
        return query_chat_agent_endpoint_and_render(input_messages)
    else:  # chat/completions
        return query_chat_completions_endpoint_and_render(input_messages)


def query_chat_completions_endpoint_and_render(input_messages):
    """Handle ChatCompletions streaming format."""
    with st.chat_message("assistant"):
        response_area = st.empty()
        response_area.markdown("_Thinking..._")
        
        accumulated_content = ""
        request_id = None
        
        try:
            for chunk in query_endpoint_stream(
                endpoint_name=SERVING_ENDPOINT,
                messages=input_messages,
                return_traces=ENDPOINT_SUPPORTS_FEEDBACK
            ):
                if "choices" in chunk and chunk["choices"]:
                    delta = chunk["choices"][0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        accumulated_content += content
                        response_area.markdown(accumulated_content)
                
                if "databricks_output" in chunk:
                    req_id = chunk["databricks_output"].get("databricks_request_id")
                    if req_id:
                        request_id = req_id
            
            return AssistantResponse(
                messages=[{"role": "assistant", "content": accumulated_content}],
                request_id=request_id
            )
        except Exception:
            response_area.markdown("_Ran into an error. Retrying without streaming..._")
            messages, request_id = query_endpoint(
                endpoint_name=SERVING_ENDPOINT,
                messages=input_messages,
                return_traces=ENDPOINT_SUPPORTS_FEEDBACK
            )
            response_area.empty()
            with response_area.container():
                for message in messages:
                    render_message(message)
            return AssistantResponse(messages=messages, request_id=request_id)


def query_chat_agent_endpoint_and_render(input_messages):
    """Handle ChatAgent streaming format."""
    from mlflow.types.agent import ChatAgentChunk
    
    with st.chat_message("assistant"):
        response_area = st.empty()
        response_area.markdown("_Thinking..._")
        
        message_buffers = OrderedDict()
        request_id = None
        
        try:
            for raw_chunk in query_endpoint_stream(
                endpoint_name=SERVING_ENDPOINT,
                messages=input_messages,
                return_traces=ENDPOINT_SUPPORTS_FEEDBACK
            ):
                response_area.empty()
                chunk = ChatAgentChunk.model_validate(raw_chunk)
                delta = chunk.delta
                message_id = delta.id

                req_id = raw_chunk.get("databricks_output", {}).get("databricks_request_id")
                if req_id:
                    request_id = req_id
                if message_id not in message_buffers:
                    message_buffers[message_id] = {
                        "chunks": [],
                        "render_area": st.empty(),
                    }
                message_buffers[message_id]["chunks"].append(chunk)
                
                partial_message = reduce_chat_agent_chunks(message_buffers[message_id]["chunks"])
                render_area = message_buffers[message_id]["render_area"]
                message_content = partial_message.model_dump_compat(exclude_none=True)
                with render_area.container():
                    render_message(message_content)
            
            messages = []
            for msg_id, msg_info in message_buffers.items():
                messages.append(reduce_chat_agent_chunks(msg_info["chunks"]))
            
            return AssistantResponse(
                messages=[message.model_dump_compat(exclude_none=True) for message in messages],
                request_id=request_id
            )
        except Exception:
            response_area.markdown("_Ran into an error. Retrying without streaming..._")
            messages, request_id = query_endpoint(
                endpoint_name=SERVING_ENDPOINT,
                messages=input_messages,
                return_traces=ENDPOINT_SUPPORTS_FEEDBACK
            )
            response_area.empty()
            with response_area.container():
                for message in messages:
                    render_message(message)
            return AssistantResponse(messages=messages, request_id=request_id)


def query_responses_endpoint_and_render(input_messages):
    """Handle ResponsesAgent streaming format using MLflow types."""
    from mlflow.types.responses import ResponsesAgentStreamEvent
    
    with st.chat_message("assistant"):
        response_area = st.empty()
        response_area.markdown("_Thinking..._")
        
        # Track all the messages that need to be rendered in order
        all_messages = []
        request_id = None

        try:
            for raw_event in query_endpoint_stream(
                endpoint_name=SERVING_ENDPOINT,
                messages=input_messages,
                return_traces=ENDPOINT_SUPPORTS_FEEDBACK
            ):
                # Extract databricks_output for request_id
                if "databricks_output" in raw_event:
                    req_id = raw_event["databricks_output"].get("databricks_request_id")
                    if req_id:
                        request_id = req_id
                
                # Parse using MLflow streaming event types, similar to ChatAgentChunk
                if "type" in raw_event:
                    event = ResponsesAgentStreamEvent.model_validate(raw_event)
                    
                    if hasattr(event, 'item') and event.item:
                        item = event.item  # This is a dict, not a parsed object
                        
                        if item.get("type") == "message":
                            # Extract text content from message if present
                            content_parts = item.get("content", [])
                            for content_part in content_parts:
                                if content_part.get("type") == "output_text":
                                    text = content_part.get("text", "")
                                    if text:
                                        all_messages.append({
                                            "role": "assistant",
                                            "content": text
                                        })
                            
                        elif item.get("type") == "function_call":
                            # Tool call
                            call_id = item.get("call_id")
                            function_name = item.get("name")
                            arguments = item.get("arguments", "")
                            
                            # Add to messages for history
                            all_messages.append({
                                "role": "assistant",
                                "content": "",
                                "tool_calls": [{
                                    "id": call_id,
                                    "type": "function",
                                    "function": {
                                        "name": function_name,
                                        "arguments": arguments
                                    }
                                }]
                            })
                            
                        elif item.get("type") == "function_call_output":
                            # Tool call output/result
                            call_id = item.get("call_id")
                            output = item.get("output", "")
                            
                            # Add to messages for history
                            all_messages.append({
                                "role": "tool",
                                "content": output,
                                "tool_call_id": call_id
                            })
                
                # Update the display by rendering all accumulated messages
                if all_messages:
                    with response_area.container():
                        for msg in all_messages:
                            render_message(msg)

            return AssistantResponse(messages=all_messages, request_id=request_id)
        except Exception:
            response_area.markdown("_Ran into an error. Retrying without streaming..._")
            messages, request_id = query_endpoint(
                endpoint_name=SERVING_ENDPOINT,
                messages=input_messages,
                return_traces=ENDPOINT_SUPPORTS_FEEDBACK
            )
            response_area.empty()
            with response_area.container():
                for message in messages:
                    render_message(message)
            return AssistantResponse(messages=messages, request_id=request_id)


# --- Init state ---
if "history" not in st.session_state:
    st.session_state.history = []

# Display logo only
st.image(current_config["logo_path"], width=200)

# Create tabs
tab1, tab2 = st.tabs(["📊 Dashboard", "💬 AI Assistant"])

# Tab 1: Databricks Dashboard
with tab1:
    st.markdown("### Databricks AI BI Dashboard")
    st.markdown("---")
    
    # Embed the Databricks dashboard
    dashboard_html = """
    <iframe
      src="https://e2-demo-west.cloud.databricks.com/embed/dashboardsv3/01f0696d102b145daeaec62e58c49c22?o=2556758628403379"
      width="100%"
      height="800"
      frameborder="0"
      style="border: 1px solid #ddd; border-radius: 8px;">
    </iframe>
    """
    st.markdown(dashboard_html, unsafe_allow_html=True)

# Tab 2: AI Chatbot
with tab2:
    st.markdown("### Chat with the AI Assistant")
    st.markdown("---")
    
    # --- Render chat history FIRST (appears above input) ---
    for i, element in enumerate(st.session_state.history):
        element.render(i)
    
    # --- Chat input at bottom (only in AI Assistant tab) ---
    prompt = st.chat_input(current_config["chat_input_placeholder"])
    if prompt:
        # Get the task type for this endpoint
        task_type = _get_endpoint_task_type(SERVING_ENDPOINT)
        
        # Add user message to chat history
        user_msg = UserMessage(content=prompt)
        st.session_state.history.append(user_msg)

        # Convert history to standard chat message format for the query methods
        input_messages = [msg for elem in st.session_state.history for msg in elem.to_input_messages()]
        
        # Handle the response using the appropriate handler
        assistant_response = query_endpoint_and_render(task_type, input_messages)
        
        # Add assistant response to history
        st.session_state.history.append(assistant_response)
        
        # Rerun to display new messages
        st.rerun()
