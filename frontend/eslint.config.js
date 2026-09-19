import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    rules: {
      // Context providers deliberately live next to their hook and helper
      // exports (lib/lang.tsx, lib/theme.tsx, lib/trail.tsx, lib/domains.tsx).
      // Fast Refresh then does a full reload for those files in dev — a DX
      // cost, not a defect. Keep the hint visible; don't fail the build.
      'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
      // React Compiler diagnostics not yet worked through. Visible, not
      // blocking. react-hooks/set-state-in-effect stays an error.
      'react-hooks/purity': 'warn',
      'react-hooks/immutability': 'warn',
      'react-hooks/preserve-manual-memoization': 'warn',
    },
  },
])
