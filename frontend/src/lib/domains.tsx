import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { api, type Domain } from './api';

/** "Nessun filtro": falsy, così i client API omettono del tutto il parametro. */
export const ALL_DOMAINS = '';

interface DomainsContextValue {
  domains: Domain[];
  current: string;
  setCurrent: (id: string) => void;
  reload: () => void;
}

const DomainsContext = createContext<DomainsContextValue>({
  domains: [],
  current: ALL_DOMAINS,
  setCurrent: () => {},
  reload: () => {},
});

export function DomainsProvider({ children }: { children: ReactNode }) {
  const [domains, setDomains] = useState<Domain[]>([]);
  const [current, setCurrent] = useState<string>(ALL_DOMAINS);

  const reload = () => {
    api.listDomains()
      .then(setDomains)
      .catch(() => setDomains([]));
  };

  useEffect(() => {
    reload();
  }, []);

  return (
    <DomainsContext.Provider value={{ domains, current, setCurrent, reload }}>
      {children}
    </DomainsContext.Provider>
  );
}

export function useDomains() {
  return useContext(DomainsContext);
}
