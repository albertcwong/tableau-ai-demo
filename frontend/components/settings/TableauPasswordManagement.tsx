'use client';

import {
  userSettingsApi,
  type UserTableauPassword,
  type CreateTableauPassword,
} from '@/lib/api';
import { TableauCredentialManagement, type CredentialConfig } from './TableauCredentialManagement';

const PASSWORD_CONFIG: CredentialConfig<UserTableauPassword, CreateTableauPassword> = {
  title: 'Tableau Username/Password',
  description:
    'Manage credentials for Tableau servers that support standard authentication. Add credentials to connect using username and password.',
  listLabel: 'Configured credentials',
  addLabel: 'Add credentials',
  emptyConfigMessage:
    'No Tableau servers have standard authentication enabled. Ask your administrator to enable it in the Admin panel.',
  deleteConfirm:
    'Remove these credentials? You will need to reconfigure to use username/password authentication.',
  configFilter: (c) => !!c.allow_standard_auth,
  listApi: userSettingsApi.listTableauPasswords,
  createApi: userSettingsApi.createTableauPassword,
  deleteApi: userSettingsApi.deleteTableauPassword,
  displayField: 'tableau_username',
  formFields: [
    { key: 'tableau_username', label: 'Tableau username', placeholder: 'tableau_username' },
    { key: 'password', label: 'Password', placeholder: 'Your Tableau password', type: 'password' },
  ],
  getInitialForm: () => ({
    tableau_server_config_id: 0,
    tableau_username: '',
    password: '',
  }),
};

export function TableauPasswordManagement() {
  return <TableauCredentialManagement config={PASSWORD_CONFIG} />;
}
