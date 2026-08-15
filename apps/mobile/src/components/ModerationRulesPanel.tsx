import { StyleSheet, Text, View } from 'react-native';

import { colors, ModerationRule } from '../constants/theme';

type Props = {
  rules?: ModerationRule[] | null;
  decision?: string | null;
  reason?: string | null;
  whatHappens?: string | null;
  labels?: string[] | null;
  compact?: boolean;
};

function outcomeColor(outcome: string) {
  const o = outcome.toLowerCase();
  if (o === 'approve' || o === 'publish') return colors.success;
  if (o === 'reject') return colors.danger;
  if (o === 'catalog') return colors.muted;
  return colors.accent;
}

export function ModerationRulesPanel({
  rules,
  decision,
  reason,
  whatHappens,
  labels,
  compact,
}: Props) {
  if (!rules?.length && !decision && !whatHappens) return null;

  return (
    <View style={[styles.wrap, compact && styles.wrapCompact]}>
      <Text style={styles.heading}>YOLO rules</Text>
      {decision ? (
        <Text style={styles.decision}>
          Decision: <Text style={{ color: outcomeColor(decision), fontWeight: '700' }}>{decision}</Text>
        </Text>
      ) : null}
      {reason ? <Text style={styles.reason}>{reason}</Text> : null}
      {labels?.length ? <Text style={styles.labels}>Detected: {labels.join(', ')}</Text> : null}

      {(rules || []).map((rule) => (
        <View key={rule.rule_name} style={styles.ruleRow}>
          <View style={styles.ruleHeader}>
            <Text style={styles.ruleName}>{rule.rule_name}</Text>
            <Text style={[styles.ruleOutcome, { color: outcomeColor(rule.outcome) }]}>
              {rule.outcome === 'catalog'
                ? 'rule'
                : `${rule.outcome}${typeof rule.confidence === 'number' ? ` · ${Math.round(rule.confidence * 100)}%` : ''}`}
            </Text>
          </View>
          {rule.description ? <Text style={styles.ruleDesc}>{rule.description}</Text> : null}
          {rule.details && Object.keys(rule.details).length > 0 ? (
            <Text style={styles.ruleDetails}>
              {Object.entries(rule.details)
                .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : String(v)}`)
                .join(' · ')}
            </Text>
          ) : null}
          {rule.outcome !== 'approve' &&
          rule.outcome !== 'publish' &&
          rule.outcome !== 'catalog' &&
          rule.on_fail ? (
            <Text style={styles.onFail}>If this fails: {rule.on_fail}</Text>
          ) : null}
          {rule.outcome === 'catalog' && rule.on_fail ? (
            <Text style={styles.onFail}>If this fails: {rule.on_fail}</Text>
          ) : null}
        </View>
      ))}

      {whatHappens ? (
        <View style={styles.outcomeBox}>
          <Text style={styles.outcomeLabel}>What happens</Text>
          <Text style={styles.outcomeBody}>{whatHappens}</Text>
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    marginTop: 18,
    marginHorizontal: 16,
    padding: 14,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.surface,
  },
  wrapCompact: {
    marginHorizontal: 0,
    marginTop: 0,
    marginBottom: 16,
  },
  heading: { fontSize: 15, fontWeight: '700', color: colors.ink, marginBottom: 8 },
  decision: { fontSize: 13, color: colors.ink, marginBottom: 4 },
  reason: { fontSize: 13, color: colors.muted, marginBottom: 6, lineHeight: 18 },
  labels: { fontSize: 12, color: colors.muted, marginBottom: 10 },
  ruleRow: {
    paddingVertical: 10,
    borderTopWidth: 1,
    borderTopColor: colors.line,
  },
  ruleHeader: { flexDirection: 'row', justifyContent: 'space-between', gap: 10, flexWrap: 'wrap' },
  ruleName: { fontSize: 13, fontWeight: '700', color: colors.ink },
  ruleOutcome: { fontSize: 12, fontWeight: '700', textTransform: 'uppercase' },
  ruleDesc: { marginTop: 4, fontSize: 12, color: colors.muted, lineHeight: 17 },
  ruleDetails: { marginTop: 4, fontSize: 12, color: colors.ink, lineHeight: 17 },
  onFail: { marginTop: 4, fontSize: 12, color: colors.danger, lineHeight: 17 },
  outcomeBox: {
    marginTop: 12,
    padding: 12,
    borderRadius: 8,
    backgroundColor: colors.accentSoft,
  },
  outcomeLabel: { fontSize: 12, fontWeight: '700', color: colors.accent, marginBottom: 4 },
  outcomeBody: { fontSize: 13, color: colors.ink, lineHeight: 19 },
});
