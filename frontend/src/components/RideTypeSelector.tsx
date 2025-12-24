type RideType = 'friday' | 'sunday' | 'message_id'

interface RideTypeSelectorProps {
    value: RideType
    onChange: (value: RideType) => void
}

export default function RideTypeSelector({ value, onChange }: RideTypeSelectorProps) {
    return (
        <div style={{ marginBottom: '1.5em' }}>
            <label style={{ display: 'block', marginBottom: '0.75em', fontWeight: 'bold', fontSize: '1.05em' }}>
                Select Ride Type:
            </label>
            <div style={{ display: 'flex', gap: '1.5em', flexWrap: 'wrap' }}>
                <label style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.5em',
                    cursor: 'pointer',
                    padding: '0.75em 1.25em',
                    border: value === 'friday' ? '2px solid #2563eb' : '2px solid #d1d5db',
                    borderRadius: '8px',
                    background: value === 'friday' ? '#eff6ff' : 'transparent',
                    transition: 'all 0.2s'
                }}>
                    <input
                        type="radio"
                        value="friday"
                        checked={value === 'friday'}
                        onChange={(e) => onChange(e.target.value as RideType)}
                        style={{ cursor: 'pointer' }}
                    />
                    <span>
                        🎉 Friday Fellowship
                    </span>
                </label>

                <label style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.5em',
                    cursor: 'pointer',
                    padding: '0.75em 1.25em',
                    border: value === 'sunday' ? '2px solid #2563eb' : '2px solid #d1d5db',
                    borderRadius: '8px',
                    background: value === 'sunday' ? '#eff6ff' : 'transparent',
                    transition: 'all 0.2s'
                }}>
                    <input
                        type="radio"
                        value="sunday"
                        checked={value === 'sunday'}
                        onChange={(e) => onChange(e.target.value as RideType)}
                        style={{ cursor: 'pointer' }}
                    />
                    <span>
                        ⛪ Sunday Service
                    </span>
                </label>

                <label style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.5em',
                    cursor: 'pointer',
                    padding: '0.75em 1.25em',
                    border: value === 'message_id' ? '2px solid #2563eb' : '2px solid #d1d5db',
                    borderRadius: '8px',
                    background: value === 'message_id' ? '#eff6ff' : 'transparent',
                    transition: 'all 0.2s'
                }}>
                    <input
                        type="radio"
                        value="message_id"
                        checked={value === 'message_id'}
                        onChange={(e) => onChange(e.target.value as RideType)}
                        style={{ cursor: 'pointer' }}
                    />
                    <span>
                        🔢 Custom Message ID
                    </span>
                </label>
            </div>
        </div>
    )
}

export type { RideType }
