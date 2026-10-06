import { Routes } from '@angular/router';
import { ApplicationDetailPage } from './features/applications/application-detail';
import { ApplicationsPage } from './features/applications/applications';
import { JobsPage } from './features/jobs/jobs';
import { ProfilePage } from './features/profile/profile';
import { SettingsPage } from './features/settings/settings';
import { TailorPage } from './features/tailor/tailor';

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'profile' },
  { path: 'profile', component: ProfilePage },
  { path: 'jobs', component: JobsPage },
  { path: 'tailor', component: TailorPage },
  { path: 'applications', component: ApplicationsPage },
  { path: 'applications/:id', component: ApplicationDetailPage },
  { path: 'settings', component: SettingsPage },
  { path: '**', redirectTo: 'profile' },
];
