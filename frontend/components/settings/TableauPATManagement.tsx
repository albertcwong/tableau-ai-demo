'use client';

import { userSettingsApi, type UserTableauPAT, type CreateTableauPAT } from '@/lib/api';
import { TableauCredentialManagement, type CredentialConfig } from './TableauCredentialManagement';

const PAT_CONFIG: CredentialConfig<UserTableauPAT, CreateTableauPAT> = {
  title: 'Tableau Personal Access Tokens',
  description:
    'Manage PATs for Tableau servers that support PAT authentication. Add a PAT to connect using your own token instead of the Connected App.',
  listLabel: 'Configured PATs',
  addLabel: 'Add PAT',
  emptyConfigMessage:
    'No Tableau servers have PAT authentication enabled. Ask your administrator to enable it in the Admin panel.',
  deleteConfirm: 'Remove this PAT? You will need to reconfigure it to use PAT authentication.',
  configFilter: (c) => !!c.allow_pat_auth,
  listApi: userSettingsApi.listTableauPATs,
  createApi: userSettingsApi.createTableauPAT,
  deleteApi: userSettingsApi.deleteTableauPAT,
  displayField: 'pat_name',
  formFields: [
    { key: 'pat_name', label: 'PAT Name', placeholder: 'My PAT' },
    {
      key: 'pat_secret',
      label: 'PAT Secret',
      placeholder: 'Your PAT secret',
      type: 'password',
      hint: 'Create a PAT in Tableau Server: User menu → My Account Settings → Personal Access Tokens',
    },
  ],
  getInitialForm: () => ({
    tableau_server_config_id: 0,
    pat_name: '',
    pat_secret: '',
  }),
};

export function TableauPATManagement() {
  return <TableauCredentialManagement config={PAT_CONFIG} />;
}
