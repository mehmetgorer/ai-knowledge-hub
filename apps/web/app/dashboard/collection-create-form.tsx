"use client";

import { useId } from "react";

import {
  dashboardFieldClassName,
  dashboardLabelClassName,
  dashboardSecondaryButtonClassName,
} from "@/components/dashboard/ui";
import {
  createCollection,
  validateCollectionNameInput,
} from "@/lib/api/client";

type CollectionCreateFormProps = {
  nameInput: string;
  onNameInputChange: (value: string) => void;
  formError: string | null;
  onFormErrorChange: (message: string | null) => void;
  isCreating: boolean;
  onCreatingChange: (creating: boolean) => void;
  onReloadCollections: (options?: { silent?: boolean }) => Promise<void>;
  disabled: boolean;
  submitLabel?: string;
};

export function CollectionCreateForm(props: CollectionCreateFormProps) {
  const nameFieldId = useId();

  async function handleCreate(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (props.isCreating || props.disabled) {
      return;
    }

    props.onFormErrorChange(null);
    const validated = validateCollectionNameInput(props.nameInput);
    if (!validated) {
      props.onFormErrorChange("Enter a non-empty name (max 255 characters).");
      return;
    }

    props.onCreatingChange(true);
    const result = await createCollection(validated);
    props.onCreatingChange(false);

    if (!result.ok) {
      props.onFormErrorChange(result.error.message);
      return;
    }

    props.onNameInputChange("");
    await props.onReloadCollections({ silent: true });
  }

  return (
    <form className="space-y-2" onSubmit={handleCreate}>
      <label htmlFor={nameFieldId} className={dashboardLabelClassName}>
        Collection name
      </label>
      <input
        id={nameFieldId}
        name="name"
        type="text"
        required
        maxLength={255}
        autoComplete="off"
        disabled={props.isCreating || props.disabled}
        value={props.nameInput}
        onChange={(event) => {
          props.onNameInputChange(event.target.value);
          props.onFormErrorChange(null);
        }}
        className={dashboardFieldClassName}
        placeholder="Research notes"
      />
      <button
        type="submit"
        disabled={props.isCreating || props.disabled}
        className={`${dashboardSecondaryButtonClassName} w-full sm:w-auto`}
      >
        {props.isCreating
          ? "Creating…"
          : (props.submitLabel ?? "Create collection")}
      </button>
      {props.formError ? (
        <p className="text-xs text-red-600 dark:text-red-400" role="alert">
          {props.formError}
        </p>
      ) : null}
    </form>
  );
}
