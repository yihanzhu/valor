#!/usr/bin/env bash
# Valor SessionStart hook: checks time and state to suggest auto-triggers.
# Stdout is injected into the Claude Code conversation context.
set -euo pipefail

STATE_FILE="${HOME}/.valor/state.json"

if [ ! -f "$STATE_FILE" ]; then
  exit 0
fi

coaching_mode=$(python3 -c "
import json, sys
try:
    state = json.load(open('$STATE_FILE'))
    print(state.get('coaching_mode', 'ambient'))
except Exception:
    print('ambient')
" 2>/dev/null || echo "ambient")

if [ "$coaching_mode" = "off" ]; then
  exit 0
fi

python3 -c "
import json, sys
from datetime import datetime, date

state_file = '$STATE_FILE'
try:
    state = json.load(open(state_file))
except Exception:
    sys.exit(0)

now = datetime.now()
today = date.today()
weekday = now.weekday()  # 0=Monday, 6=Sunday

if weekday > 4:
    sys.exit(0)

hour = now.hour
suggest_before = state.get('briefing_suggest_before', 11)
suggest_after = state.get('wrapup_suggest_after', 17)

last_briefing = state.get('last_briefing_date', '')
last_wrapup = state.get('last_wrapup_date', '')
last_reflection_week = state.get('last_reflection_week', -1)

today_str = today.isoformat()
current_week = today.isocalendar()[1]

suggestions = []

if hour < suggest_before and last_briefing != today_str:
    suggestions.append('[Valor] Good morning! Ready for your daily briefing? (say \"briefing\" or \"skip\")')

if weekday == 4 and last_reflection_week != current_week:
    suggestions.append('[Valor] It\\'s Friday -- want your weekly reflection? (say \"weekly\" or \"skip\")')

if hour >= suggest_after and last_wrapup != today_str:
    suggestions.append('[Valor] End of day -- ready for your wrap-up? (say \"wrap up\" or \"skip\")')

if suggestions:
    print('\\n'.join(suggestions))
" 2>/dev/null

exit 0
