import { fileURLToPath, pathToFileURL } from 'node:url';
const FRONT = fileURLToPath(new URL('../', import.meta.url)).replace(/\/$/, '');
export async function resolve(specifier, context, next) {
  if (specifier.startsWith('/js/')) return next(pathToFileURL(FRONT + specifier).href, context);
  return next(specifier, context);
}
