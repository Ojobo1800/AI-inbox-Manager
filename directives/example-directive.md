# Directive: Example Data Processing

## Goal
Process incoming data records, validate them, and store results in the appropriate format.

## Inputs
- **data_source**: Path to input data file or API endpoint
- **validation_rules**: Set of validation criteria to apply
- **output_format**: Desired output format (JSON, CSV, etc.)

## Outputs
- **processed_data**: Validated and transformed data
- **validation_report**: Summary of any validation errors
- **success_count**: Number of successfully processed records

## Steps

1. **Load input data**
   - Read data from specified source
   - Handle common file formats (JSON, CSV)
   - Log source information

2. **Validate each record**
   - Apply validation rules from config
   - Collect validation errors
   - Continue processing valid records

3. **Transform data**
   - Apply business logic transformations
   - Normalize formats
   - Calculate derived fields

4. **Store results**
   - Write to specified output location
   - Generate validation report
   - Log completion metrics

## Edge Cases

- **Empty input file**: Log warning, create empty output, report zero records
- **All records invalid**: Generate error report, alert monitoring, don't fail completely
- **Network timeout**: Retry 3 times with exponential backoff, then fail gracefully
- **Duplicate records**: Use deduplication strategy from config (keep first, keep last, merge)

## Safety Constraints

- **Never overwrite** existing output without backup
- **Never process** production data in test environment
- **Always validate** file permissions before writing
- **Always log** processing metrics for auditing

## Related Scripts

- `execution/process_data.py` - Main processing logic
- `execution/validate_records.py` - Validation functions
- `execution/transform_data.py` - Transformation utilities

## Monitoring

- Track processing time per record
- Alert if error rate exceeds 10%
- Log all file operations
- Report daily summary statistics

## Testing Strategy

- Unit tests verify validation logic
- Integration tests use sample data files
- Never test with real customer data
