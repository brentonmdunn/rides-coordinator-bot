import { useEffect, useState } from 'react';
import { apiFetch } from '../lib/api';

const EnvironmentBanner = () => {
    const [appEnv, setAppEnv] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchEnvironment = async () => {
            try {
                const response = await apiFetch('/api/environment');
                const data = await response.json();
                setAppEnv(data.environment);
            } catch (error) {
                console.error('Failed to fetch environment:', error);
                // Default to local if fetch fails
                setAppEnv('local');
            } finally {
                setLoading(false);
            }
        };

        fetchEnvironment();
    }, []);

    // Don't render anything while loading
    if (loading) {
        return null;
    }

    // Only show banner for preprod (hide for both local and prod)
    if (!appEnv || appEnv === 'local' || appEnv === 'prod') {
        return null;
    }

    // Determine banner styles based on environment
    const getEnvironmentStyles = () => {
        if (appEnv === 'preprod') {
            return {
                bg: 'bg-yellow-500 dark:bg-yellow-600',
                text: 'Pre-Production',
            };
        }

        // Fallback for any other non-local/non-prod environment
        return {
            bg: 'bg-purple-600 dark:bg-purple-700',
            text: appEnv.toUpperCase(),
        };
    };

    const { bg, text } = getEnvironmentStyles();

    return (
        <div className={`${bg} text-white py-2 px-4 text-center font-medium text-sm sticky top-0 z-50 shadow-md`}>
            Environment: <span className="font-bold">{text}</span>
        </div>
    );
};

export default EnvironmentBanner;
