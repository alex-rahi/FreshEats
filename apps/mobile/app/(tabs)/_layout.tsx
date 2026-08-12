import { Tabs } from 'expo-router';
import { Text } from 'react-native';

import { colors } from '../../src/constants/theme';

function TabLabel({ label, focused }: { label: string; focused: boolean }) {
  return (
    <Text style={{ fontSize: 11, fontWeight: focused ? '700' : '500', color: focused ? colors.accent : colors.muted }}>
      {label}
    </Text>
  );
}

export default function TabsLayout() {
  return (
    <Tabs
      screenOptions={{
        headerStyle: { backgroundColor: colors.bg },
        headerTitleStyle: { fontWeight: '700', letterSpacing: -0.4 },
        tabBarStyle: {
          backgroundColor: colors.surface,
          borderTopColor: colors.line,
        },
        tabBarActiveTintColor: colors.accent,
        tabBarInactiveTintColor: colors.muted,
      }}
    >
      <Tabs.Screen
        name="grid"
        options={{
          title: 'FreshEats',
          tabBarLabel: ({ focused }) => <TabLabel label="Grid" focused={focused} />,
          tabBarIcon: () => <Text>▦</Text>,
        }}
      />
      <Tabs.Screen
        name="upload"
        options={{
          title: 'Upload',
          tabBarLabel: ({ focused }) => <TabLabel label="Upload" focused={focused} />,
          tabBarIcon: () => <Text>＋</Text>,
        }}
      />
      <Tabs.Screen
        name="profile"
        options={{
          title: 'Profile',
          tabBarLabel: ({ focused }) => <TabLabel label="Profile" focused={focused} />,
          tabBarIcon: () => <Text>◎</Text>,
        }}
      />
    </Tabs>
  );
}
