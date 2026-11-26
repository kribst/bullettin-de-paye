import { useState } from "react";
import { Navigate } from "react-router-dom";
import { KeyRound, UserPlus, Users } from "lucide-react";
import { api } from "../../api.js";
import { useAuth } from "../../auth.jsx";
import { useI18n } from "../../i18n.jsx";
import { Async, Empty, Field, FormModal, Input, PasswordReveal, Person, Select, useApi, useToast } from "../../ui.jsx";

const ORDINARY_ROLES = [
  ["hr_manager", "accounts.role_hr"],
  ["payroll_manager", "accounts.role_payroll"],
  ["manager", "accounts.role_manager"],
  ["employee", "accounts.role_employee"],
  ["auditor", "accounts.role_auditor"],
];

function AccountForm({ onClose, onSaved }) {
  const { t } = useI18n();
  return (
    <FormModal title={t("accounts.create")} onClose={onClose} submitLabel={t("accounts.create")}
      submit={async (fd) => {
        const data = Object.fromEntries([...fd.entries()].filter(([, value]) => value !== ""));
        data.must_change_password = true;
        onSaved(await api.post("/accounts/users/", data));
      }}>
      <div className="form-grid">
        <Field label={t("field.first_name")} name="first_name"><Input name="first_name" required /></Field>
        <Field label={t("field.last_name")} name="last_name"><Input name="last_name" required /></Field>
        <Field label={t("field.email")} name="email" full><Input name="email" type="email" required /></Field>
        <Field label={t("accounts.password")} name="password" full><Input name="password" type="password" required minLength={8} /></Field>
        <Field label={t("accounts.role")} name="role" full>
          <Select name="role" required placeholder={t("common.choose")}
            options={ORDINARY_ROLES.map(([value, key]) => [value, t(key)])} />
        </Field>
      </div>
    </FormModal>
  );
}

export default function Accounts() {
  const { isCompanyAdmin } = useAuth();
  const { t } = useI18n();
  const toast = useToast();
  const [creating, setCreating] = useState(false);
  const [reveal, setReveal] = useState(null);
  const list = useApi(() => api.get("/accounts/users/"));

  if (!isCompanyAdmin) return <Navigate to="/hr" replace />;

  const toggle = async (user) => {
    const path = user.is_active ? "deactivate" : "activate";
    await api.post(`/accounts/users/${user.id}/${path}/`);
    list.reload();
  };

  const resetPassword = async (user) => {
    const result = await api.post(`/accounts/users/${user.id}/reset-password/`);
    setReveal({ name: `${user.first_name} ${user.last_name}`, password: result.temporary_password, email: user.email });
  };

  return (
    <>
      <div className="page-head">
        <div><h1>{t("accounts.title")}</h1><p>{t("accounts.sub")}</p></div>
        <button className="btn primary" onClick={() => setCreating(true)}><UserPlus size={16} />{t("accounts.create")}</button>
      </div>
      <div className="card">
        <Async q={list}>
          {(rows) => rows.length ? (
            <div className="table-wrap">
              <table className="table">
                <thead><tr><th>{t("accounts.user")}</th><th>{t("accounts.role")}</th><th>{t("accounts.status")}</th><th></th></tr></thead>
                <tbody>
                  {rows.map((u) => (
                    <tr key={u.id}>
                      <td><Person first={u.first_name} last={u.last_name} sub={u.email} /></td>
                      <td>{t(ORDINARY_ROLES.find(([value]) => value === u.role)?.[1] || u.role)}</td>
                      <td><span className={"badge " + (u.is_active ? "green" : "red")}>{u.is_active ? t("accounts.active") : t("accounts.inactive")}</span></td>
                      <td>
                        <div className="row" style={{ justifyContent: "flex-end" }}>
                          <button className="btn ghost sm" onClick={() => resetPassword(u)}><KeyRound size={15} />{t("accounts.reset")}</button>
                          <button className={"btn sm " + (u.is_active ? "danger" : "success")} onClick={() => toggle(u)}>
                            {u.is_active ? t("accounts.deactivate") : t("accounts.activate")}
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <Empty icon={Users}>{t("accounts.empty")}</Empty>}
        </Async>
      </div>
      {creating && (
        <AccountForm onClose={() => setCreating(false)} onSaved={(user) => {
          setCreating(false);
          toast(t("accounts.created", { email: user.email }));
          list.reload();
        }} />
      )}
      {reveal && (
        <PasswordReveal name={`${reveal.name} (${reveal.email})`} password={reveal.password} onClose={() => setReveal(null)} />
      )}
    </>
  );
}
