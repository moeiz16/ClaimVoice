import js from '@eslint/js'
import pluginVue from 'eslint-plugin-vue'
import globals from 'globals'
import tseslint from 'typescript-eslint'

export default tseslint.config(
  { ignores: ['.nuxt/**', '.output/**', 'node_modules/**', 'dist/**'] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  ...pluginVue.configs['flat/recommended'],
  {
    files: ['**/*.vue'],
    languageOptions: { parserOptions: { parser: tseslint.parser } },
  },
  {
    languageOptions: { globals: { ...globals.browser, ...globals.node } },
    rules: {
      // Nuxt auto-imports (defineNuxtConfig, useFetch, ref, …) are resolved by the type checker, not ESLint.
      'no-undef': 'off',
      'vue/multi-word-component-names': 'off',
    },
  },
)
