import { createRoot } from 'react-dom/client';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider, ProtectedRoute, RoleGuard } from './auth';
import { NewAccountPage, AccountDetailPage } from './AccountPages';
import { OperationsPage, AuditPage } from './OperationsPages';
import { BeneficiariesPage, NewBeneficiaryPage } from './BeneficiaryPages';
import { AdvancedHistoryPage, StatementsPage } from './ReportingPages';
import { SchedulesPage, NewSchedulePage, ScheduleDetailPage } from './SchedulePages';
import { InboxPage } from './InboxPage';
import { AppShell } from './components/AppShell';
import {
  AboutPage,
  AccountsPage,
  DashboardPage,
  HistoryPage,
  LoginPage,
  NewTransferPage,
  NotFoundPage,
  ReceiptPage,
} from './pages';
import './styles.css';

const client = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 15000, refetchOnWindowFocus: false } },
});
createRoot(document.getElementById('root')!).render(
  <QueryClientProvider client={client}>
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<ProtectedRoute />}>
            <Route element={<AppShell />}>
              <Route index element={<DashboardPage />} />
              <Route element={<RoleGuard roles={['CUSTOMER']} />}>
                <Route path="accounts" element={<AccountsPage />} />
                <Route path="accounts/new" element={<NewAccountPage />} />
                <Route path="accounts/:id" element={<AccountDetailPage />} />
                <Route path="beneficiaries" element={<BeneficiariesPage />} />
                <Route path="beneficiaries/new" element={<NewBeneficiaryPage />} />
                <Route path="statements" element={<StatementsPage />} />
                <Route path="scheduled-transfers" element={<SchedulesPage />} />
                <Route path="scheduled-transfers/new" element={<NewSchedulePage />} />
                <Route path="scheduled-transfers/:id" element={<ScheduleDetailPage />} />
                <Route path="notifications" element={<InboxPage />} />
                <Route path="transfers/search" element={<AdvancedHistoryPage />} />
                <Route path="transfers" element={<HistoryPage />} />
                <Route path="transfers/new" element={<NewTransferPage />} />
                <Route path="transfers/:id" element={<ReceiptPage />} />
              </Route>
              <Route element={<RoleGuard roles={['OPERATIONS']} />}>
                <Route path="ops" element={<OperationsPage />} />
              </Route>
              <Route element={<RoleGuard roles={['OPERATIONS', 'AUDITOR']} />}>
                <Route path="audit" element={<AuditPage />} />
              </Route>
              <Route path="about" element={<AboutPage />} />
              <Route path="*" element={<NotFoundPage />} />
            </Route>
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  </QueryClientProvider>,
);
