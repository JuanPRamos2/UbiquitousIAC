const DEFAULT_CONFIGURATION = {
  baseUrl: 'http://34.51.99.221:5001',
  endpoint: '/books',
  pageSize: 8,
};

const STORAGE_KEY = 'library-catalog-configuration';

export const loadConfiguration = () => {
  try {
    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
    return { ...DEFAULT_CONFIGURATION, ...stored };
  } catch {
    return { ...DEFAULT_CONFIGURATION };
  }
};

export const saveConfiguration = (configuration) => {
  const normalized = {
    baseUrl: configuration.baseUrl.trim().replace(/\/$/, ''),
    endpoint: configuration.endpoint.trim().startsWith('/')
      ? configuration.endpoint.trim()
      : `/${configuration.endpoint.trim()}`,
    pageSize: Math.min(48, Math.max(1, Number(configuration.pageSize) || DEFAULT_CONFIGURATION.pageSize)),
  };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(normalized));
  return normalized;
};

export const getBooksUrl = (configuration, page, pageSize) => {
  const url = new URL(`${configuration.baseUrl}${configuration.endpoint}`);
  url.searchParams.set('page', String(page));
  url.searchParams.set('limit', String(pageSize));
  return url.toString();
};
