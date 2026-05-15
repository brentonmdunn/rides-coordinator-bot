import { Input } from '../ui/input'
import InsetPanel from './InsetPanel'
import LabeledField from './LabeledField'

interface ChannelIdFieldProps {
    value: string
    onChange: (value: string) => void
    label?: string
    placeholder?: string
    hint?: string
}

/**
 * Optional Discord channel-ID input shown inside the "Advanced Settings"
 * panel for Pickup Locations / Group Rides.
 */
function ChannelIdField({
    value,
    onChange,
    label = 'Custom Channel ID (Optional)',
    placeholder = 'Default: Rides Announcements Channel',
    hint = 'Leave blank to use the default channel.',
}: ChannelIdFieldProps) {
    return (
        <InsetPanel animated>
            <LabeledField label={label} hint={hint}>
                <Input
                    type="text"
                    value={value}
                    onChange={(e) => onChange(e.target.value)}
                    placeholder={placeholder}
                    className="w-full max-w-md font-mono text-sm"
                />
            </LabeledField>
        </InsetPanel>
    )
}

export default ChannelIdField
