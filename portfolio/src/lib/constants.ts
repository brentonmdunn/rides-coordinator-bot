// Timing
export const QUERY_STALE_5_MIN = 5 * 60 * 1000;
export const QUERY_STALE_1_MIN = 60_000;
export const COPY_FEEDBACK_MS = 2000;
export const HINT_MESSAGE_MS = 1500;
export const LOCATION_TOGGLE_DELAY_MS = 400;
export const ROUTE_GENERATION_DEBOUNCE_MS = 300;
export const INPUT_FOCUS_DELAY_MS = 30;

// Pagination
export const UPCOMING_DATES_PAGE_SIZE = 4;

// Map / route builder
export const MAP_INITIAL_ZOOM = 14;
export const MAP_SMOOTH_WHEEL_ZOOM = 1.5;
export const MAP_FIT_BOUNDS_PADDING = 50;
export const MAP_FIT_BOUNDS_DURATION = 0.8;
export const MAP_PADDING_FRACTION = 0.1;
export const MAP_PADDING_MIN_DEGREES = 0.01;
export const ROUTE_POLYLINE_WEIGHT = 4;
export const ROUTE_POLYLINE_OPACITY = 0.8;
export const TOOLTIP_OFFSET_SELECTED = -10;
export const TOOLTIP_OFFSET_UNSELECTED = -36;

// Layout
export const MENTION_DROPDOWN_MAX_HEIGHT = 152;
export const MENTION_DROPDOWN_LINE_HEIGHT_FALLBACK = 20;
export const MENTION_DROPDOWN_OFFSET = 4;

// Coverage
export const COVERAGE_PERCENTAGE_MULTIPLIER = 100;

// Day-of-week thresholds (getDay() values)
export const DAY_SUNDAY = 0;
export const DAY_FRIDAY = 5;
export const DAY_SATURDAY = 6;

// Hour thresholds for automatic day logic
export const SUNDAY_WIDGET_START_HOUR = 16;   // Saturday 4 PM
export const SUNDAY_WIDGET_END_HOUR = 13;     // Sunday 1 PM
export const FRIDAY_WARNING_HOUR = 12;        // Friday noon
export const SUNDAY_WARNING_HOUR = 17;        // Sunday 5 PM

// Time conversion
export const SECONDS_PER_MINUTE = 60;
export const MINUTES_PER_HOUR = 60;

// Local storage / URL param keys
export const ROUTE_BUILDER_STORAGE_KEY = 'routeBuilder.state.v1';
export const RB_PARAM_STOPS = 'rb_stops';
export const RB_PARAM_TIME_MODE = 'rb_time_mode';
export const RB_PARAM_LEAVE_TIME = 'rb_leave_time';
export const RB_PARAM_DRIVER = 'rb_driver';
