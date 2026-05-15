import { Input } from '../ui/input'
import InsetPanel from './InsetPanel'
import LabeledField from './LabeledField'

interface MessageIdFieldProps {
    value: string
    onChange: (value: string) => void
    label?: string
    placeholder?: string
    required?: boolean
}

/**
 * Discord message-ID input shown when a custom message ID is selected.
 * Wraps the labeled input in an InsetPanel, matching the existing layout in
 * Pickup Locations / Group Rides.
 */
function MessageIdField({
    value,
    onChange,
    label = 'Message ID',
    placeholder = 'Enter Discord message ID',
    required = true,
}: MessageIdFieldProps) {
    return (
        <InsetPanel>
            <LabeledField label={label}>
                <Input
                    type="text"
                    value={value}
                    onChange={(e) => onChange(e.target.value)}
                    placeholder={placeholder}
                    required={required}
                    className="w-full max-w-md"
                />
            </LabeledField>
        </InsetPanel>
    )
}

export default MessageIdField
