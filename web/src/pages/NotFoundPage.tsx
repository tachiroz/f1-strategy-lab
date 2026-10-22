import { Link } from 'react-router'
import { Page, PageHeader } from '../components/PageHeader'

export function NotFoundPage() {
  return (
    <Page>
      <title>Нет такой страницы · F1 Strategy Lab</title>
      <PageHeader
        eyebrow="404"
        title="Такой страницы нет"
        description={
          <>
            Вернитесь на{' '}
            <Link to="/" className="text-ink underline decoration-line-strong underline-offset-4">
              главную
            </Link>{' '}
            или выберите раздел в меню.
          </>
        }
      />
    </Page>
  )
}
