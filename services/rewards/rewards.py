import time

# Simple rewards engine prototype

BADGE_RULES = [
    ('acidd_defender', lambda ctx: ctx.get('acid_spikes_reduced', False)),
    ('streak_7', lambda ctx: ctx.get('current_streak', 0) >= 7)
]


def evaluate_rewards(user_state, analytics):
    ctx = {**user_state, **analytics}
    earned = []
    for badge, rule in BADGE_RULES:
        try:
            if rule(ctx) and badge not in user_state.get('badges', []):
                earned.append(badge)
        except Exception:
            continue
    xp = 10 if analytics.get('improved', False) else 1
    return {'xp_delta': xp, 'new_badges': earned, 'timestamp': time.time()}


if __name__ == '__main__':
    print(evaluate_rewards({'badges': [], 'current_streak': 8}, {'improved': True}))
