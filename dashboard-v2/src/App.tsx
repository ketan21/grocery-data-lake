import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Layout } from './components/Layout';
import { OverviewPage } from './pages/OverviewPage';
import { DealsPage } from './pages/DealsPage';
import { HealthPage } from './pages/HealthPage';
import { IngredientsPage } from './pages/IngredientsPage';
import { BrandsPage } from './pages/BrandsPage';
import { CheapestPage } from './pages/CheapestPage';
import { AlternativesPage } from './pages/AlternativesPage';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter basename="/dashboard">
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<OverviewPage />} />
            <Route path="deals" element={<DealsPage />} />
            <Route path="health" element={<HealthPage />} />
            <Route path="ingredients" element={<IngredientsPage />} />
            <Route path="brands" element={<BrandsPage />} />
            <Route path="cheapest" element={<CheapestPage />} />
            <Route path="alternatives" element={<AlternativesPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}