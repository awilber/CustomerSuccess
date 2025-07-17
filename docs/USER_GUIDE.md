# CustomerSuccess User Guide

## Table of Contents

1. [Getting Started](#getting-started)
2. [Customer Management](#customer-management)
3. [Email Import & Analysis](#email-import--analysis)
4. [Timeline Visualization](#timeline-visualization)
5. [Embeddings & AI Analysis](#embeddings--ai-analysis)
6. [Advanced Features](#advanced-features)
7. [Troubleshooting](#troubleshooting)

## Getting Started

### System Requirements

- Python 3.8 or higher
- Web browser (Chrome, Firefox, Safari, or Edge)
- Internet connection (for OpenAI API features)

### Installation

1. **Download and Setup**
   ```bash
   git clone https://github.com/awilber/CustomerSuccess.git
   cd CustomerSuccess
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\\Scripts\\activate
   pip install -r requirements.txt
   ```

2. **First Run**
   ```bash
   python app.py
   ```
   The application will start on an available port (typically 5000).

3. **Initialize Database**
   - Open your browser to `http://localhost:5000`
   - Visit `http://localhost:5000/init-db` to set up sample data
   - Default customer \"HCR\" will be created

### User Interface Overview

The CustomerSuccess interface consists of several main sections:

- **Navigation Bar**: Access different modules (Customers, Timeline, Embeddings, Analytics)
- **Customer List**: View and manage all customers
- **Timeline View**: Visualize communication patterns
- **Embeddings Interface**: AI-powered email analysis
- **Analytics Dashboard**: Insights and reporting

## Customer Management

### Adding a New Customer

1. Click **\"Add Customer\"** from the main dashboard
2. Fill in the customer details:
   - **Name**: Customer organization name
   - **Description**: Optional description
3. Click **\"Create Customer\"**

### Managing Customer People

Each customer can have multiple associated people:

1. Navigate to the customer detail page
2. Click **\"Add Person\"**
3. Enter person details:
   - **Name**: Person's full name
   - **Email**: Primary email address
   - **Side**: Select \"Customer\" or \"Us\" (our team)

### Customer Overview

The customer detail page shows:
- **Basic Information**: Name, description, creation date
- **People**: All associated contacts
- **Email Statistics**: Total emails, processed emails, date ranges
- **Quick Actions**: Import emails, view timeline, process embeddings

## Email Import & Analysis

### Google Takeout Import

CustomerSuccess can import emails from Google Takeout exports:

1. **Request Google Takeout**
   - Go to [Google Takeout](https://takeout.google.com)
   - Select \"Mail\" data
   - Choose export format (ZIP recommended)
   - Download the export file

2. **Upload to CustomerSuccess**
   - Navigate to customer detail page
   - Click **\"Upload Google Takeout\"**
   - Select the downloaded ZIP file
   - Wait for processing to complete

3. **Review Import Results**
   - Check the number of emails imported
   - Verify email addresses are correctly identified
   - Review any import errors or warnings

### Email Processing

After import, emails are automatically:
- Parsed for sender, recipient, subject, and body
- Organized by date and conversation thread
- Linked to customer and person records
- Prepared for embedding analysis

## Timeline Visualization

### Accessing Timeline View

1. Navigate to a customer's detail page
2. Click **\"View Timeline\"** or use the Timeline tab
3. The timeline displays email communication patterns over time

### Timeline Features

#### Left Sidebar Filters

**Timeline Mode:**
- **By User**: Shows communication colored by person
- **By Topic**: Shows communication colored by extracted topics

**Date Range:**
- Set start and end dates for the timeline
- Useful for focusing on specific time periods

**Sender Filter:**
- Checkbox list of all email senders
- Select/deselect to include/exclude specific senders

**Recipient Filter:**
- Checkbox list of all email recipients
- Control which recipients are shown

**Quick Filters:**
- **\"Our Domains Only\"**: Show only @wiredtriangle.com and @knewvantage.com emails
- **\"Select All\"**: Include all senders and recipients
- **\"Clear All\"**: Deselect all filters

**Topics Filter** (when topics are available):
- **Main Topics**: Primary conversation themes
- **Sub Topics**: More specific topic categories
- Shows email count for each topic

#### Timeline Visualization

The timeline chart shows:
- **X-axis**: Time periods (days, weeks, months)
- **Y-axis**: Email volume
- **Colors**: Different colors for different users or topics
- **Hover Information**: Email details, subjects, and previews

#### Interactive Features

- **Zoom**: Click and drag to zoom into specific time periods
- **Pan**: Drag to move around the timeline
- **Hover**: Get detailed information about specific emails
- **Legend**: Click legend items to show/hide specific users or topics

### Timeline Interpretation

#### Communication Patterns

- **High Volume Periods**: Intense communication phases
- **Gaps**: Periods of low or no communication
- **Spikes**: Sudden increases in email activity
- **Trends**: Long-term communication patterns

#### User Analysis

- **Blue Colors**: Internal team communications
- **Green Colors**: Customer team communications
- **Color Intensity**: Indicates communication frequency

#### Topic Analysis

- **Topic Clusters**: Groups of related conversations
- **Topic Evolution**: How topics change over time
- **Topic Intensity**: Relative importance of different topics

## Embeddings & AI Analysis

### Understanding Embeddings

Embeddings are numerical representations of email content that enable:
- **Semantic Search**: Find emails by meaning, not just keywords
- **Topic Extraction**: Automatically identify conversation themes
- **Similarity Analysis**: Group related emails together
- **Trend Analysis**: Track how topics evolve over time

### Processing Embeddings

#### Accessing Embeddings Interface

1. Navigate to a customer's detail page
2. Click **\"Embeddings\"** tab or button
3. You'll see the embeddings processing interface

#### Embedding Methods

**OpenAI API (Recommended):**
- High-quality semantic understanding
- Requires OpenAI API key
- Best for topic extraction and analysis

**TF-IDF (Fallback):**
- Fast, free, local processing
- Good for keyword-based analysis
- No external API required

#### Processing Steps

1. **Select Embedding Method**
   - Choose OpenAI or TF-IDF based on your needs

2. **Configure Filters**
   - Use sender/recipient filters to focus on specific communications
   - Default filters include your organization's domains

3. **Select Time Period**
   - Choose specific years or months to process
   - See email counts for each time period
   - Process incrementally to manage resources

4. **Start Processing**
   - Click \"Process Month\" or \"Process Year\"
   - Monitor progress in real-time
   - Cancel processing if needed

#### Processing Interface

**Left Panel:**
- **Embedding Method**: Select processing approach
- **Sender/Recipient Filters**: Control which emails to process
- **Quick Filters**: Preset filter combinations
- **Topics Filter**: Filter by extracted topics (after processing)

**Right Panel:**
- **Processing Status**: Real-time progress updates
- **Year/Month Selection**: Hierarchical time period selection
- **Processing Controls**: Start, cancel, and monitor operations

### Topic Extraction

#### Automatic Topic Identification

After processing embeddings, CustomerSuccess can automatically identify:

**Main Topics (up to 10):**
- Broad conversation themes
- High-level subject areas
- Major business topics

**Sub Topics (up to 20):**
- Specific conversation details
- Narrow subject areas
- Detailed business topics

#### Topic Management

1. **Extract Topics**
   - Click \"Extract Topics from Embeddings\"
   - Wait for clustering analysis to complete
   - Review identified topics

2. **Review Topic Quality**
   - Check topic names for relevance
   - Verify email counts make sense
   - Note any obviously incorrect groupings

3. **Use Topics for Filtering**
   - Topics appear as checkboxes in filter panels
   - Select/deselect to focus on specific themes
   - Combine with other filters for precise analysis

### Advanced Embeddings Features

#### Batch Processing

- **Process All Filtered**: Process all emails matching current filters
- **Process by Year**: Process entire years at once
- **Process by Month**: Process specific months for precision

#### Progress Monitoring

- **Real-time Progress**: See processing status updates
- **Error Tracking**: Monitor processing errors
- **Skip Reporting**: Understand why emails were skipped

#### Performance Optimization

- **Skip Already Processed**: Avoid reprocessing existing embeddings
- **Batch Processing**: Efficient processing of multiple emails
- **Background Processing**: Non-blocking operations

## Advanced Features

### Search and Filtering

#### Advanced Search
- **Semantic Search**: Find emails by meaning (requires embeddings)
- **Keyword Search**: Traditional text-based search
- **Date Range Search**: Find emails within specific time periods
- **Sender/Recipient Search**: Find emails from specific people

#### Filter Combinations
- **Multiple Filters**: Combine sender, recipient, date, and topic filters
- **Saved Filters**: Save frequently used filter combinations
- **Filter Presets**: Quick access to common filter patterns

### Data Export

#### Export Formats
- **CSV**: Email data for spreadsheet analysis
- **JSON**: Structured data for further processing
- **Timeline Images**: Export timeline visualizations

#### Export Options
- **Filtered Data**: Export only emails matching current filters
- **Full Dataset**: Export all customer emails
- **Summary Reports**: Export aggregated statistics

### Integration Features

#### API Access
- **RESTful API**: Programmatic access to all features
- **Authentication**: Secure API access
- **Rate Limiting**: Controlled API usage

#### Webhook Support
- **Processing Notifications**: Get notified when processing completes
- **Data Updates**: Receive notifications about new emails
- **Error Alerts**: Get notified about processing errors

## Troubleshooting

### Common Issues

#### Application Won't Start

**Symptoms**: Error messages when running `python app.py`

**Solutions**:
1. Check Python version: `python --version` (should be 3.8+)
2. Verify virtual environment is activated
3. Reinstall dependencies: `pip install -r requirements.txt`
4. Check port availability (try different port)

#### Database Issues

**Symptoms**: Errors about missing tables or corrupted data

**Solutions**:
1. Reinitialize database: Delete `database.db` and visit `/init-db`
2. Check database permissions
3. Verify disk space availability

#### Email Import Problems

**Symptoms**: Emails not importing or processing errors

**Solutions**:
1. Verify Google Takeout file format (should be ZIP)
2. Check file size limits
3. Ensure email data is in expected format
4. Review import logs for specific errors

#### Embeddings Processing Issues

**Symptoms**: Processing fails or produces poor results

**Solutions**:
1. **OpenAI API Issues**:
   - Verify API key is correct
   - Check API quota and billing
   - Try TF-IDF method as fallback

2. **Performance Issues**:
   - Process smaller batches
   - Increase system memory
   - Check network connectivity

3. **Quality Issues**:
   - Review email text quality
   - Check for non-English content
   - Verify topic extraction parameters

#### Timeline Visualization Problems

**Symptoms**: Timeline not displaying or showing incorrect data

**Solutions**:
1. Check browser compatibility (requires modern browser)
2. Verify email data exists for selected time period
3. Review filter settings
4. Clear browser cache and cookies

### Performance Optimization

#### Large Datasets

**Recommendations**:
- Process embeddings in smaller batches
- Use date range filters to focus analysis
- Consider upgrading system memory
- Use TF-IDF for initial analysis, OpenAI for detailed work

#### Slow Response Times

**Solutions**:
- Check network connectivity
- Verify system resources
- Consider database optimization
- Review server logs for bottlenecks

### Getting Help

#### Log Files
- Check `app.log` for application errors
- Review browser console for JavaScript errors
- Monitor network requests for API issues

#### Support Resources
- GitHub repository for bug reports
- API documentation for integration help
- User community for tips and tricks

#### Contact Information
- GitHub Issues: [https://github.com/awilber/CustomerSuccess/issues]
- Email support: Create GitHub issue for fastest response

## Best Practices

### Data Management
- Regular backups of database files
- Clean up old processing tasks
- Monitor disk space usage
- Keep Google Takeout exports organized

### Performance
- Process embeddings during off-peak hours
- Use incremental processing for large datasets
- Monitor API usage and costs
- Regular database maintenance

### Security
- Keep API keys secure
- Regular software updates
- Secure server deployment
- Monitor access logs

### Workflow
- Start with small datasets for testing
- Use filters to focus analysis
- Regular topic extraction updates
- Document important findings