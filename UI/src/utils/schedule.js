const EVERYDAY = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
const WEEKDAYS = ['mon', 'tue', 'wed', 'thu', 'fri']
const APP_TIMEZONE = import.meta.env.VITE_APP_TIMEZONE

export function newScheduleDraft() {
  return {
    id: `draft_${Date.now()}_${Math.random().toString(36).slice(2)}`,
    frequency: 'weekdays',
    dates: [''],
    times: ['09:00'],
  }
}

export function buildScheduleRules(drafts) {
  const rules = []
  drafts.forEach(draft => {
    const cleanTimes = [...new Set(draft.times.map(t => String(t || '').trim()).filter(Boolean))]
    if (!cleanTimes.length) return

    if (draft.frequency === 'custom_dates') {
      const cleanDates = [...new Set(draft.dates.map(d => String(d || '').trim()).filter(Boolean))]
      cleanDates.forEach(dateValue => {
        cleanTimes.forEach(time => {
          const [hour, minute] = time.split(':').map(Number)
          if (Number.isInteger(hour) && Number.isInteger(minute)) {
            rules.push({ trigger_type: 'date', day_of_week: dateValue, hour, minute, timezone: APP_TIMEZONE })
          }
        })
      })
      return
    }

    const days = draft.frequency === 'daily' ? EVERYDAY : WEEKDAYS
    cleanTimes.forEach(time => {
      const [hour, minute] = time.split(':').map(Number)
      if (Number.isInteger(hour) && Number.isInteger(minute)) {
        rules.push({ trigger_type: 'cron', day_of_week: days.join(','), hour, minute, timezone: APP_TIMEZONE })
      }
    })
  })
  return rules
}

export function formatDays(value) {
  if (value === 'mon,tue,wed,thu,fri,sat,sun') return 'Daily'
  return String(value || '').split(',').map(d => d.charAt(0).toUpperCase() + d.slice(1)).join(', ')
}

function pad(value) {
  return String(value ?? 0).padStart(2, '0')
}

export function formatScheduleWindow(schedule) {
  const time = `${pad(schedule.hour)}:${pad(schedule.minute)}`
  if (schedule.trigger_type === 'date') return `${schedule.day_of_week} at ${time}`
  return `${formatDays(schedule.day_of_week)} at ${time}`
}

function jsDayToScheduleDay(dayIndex) {
  return ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat'][dayIndex]
}

function localDateTime(dateValue, hour, minute) {
  const [year, month, day] = String(dateValue || '').split('-').map(Number)
  return new Date(year, (month || 1) - 1, day || 1, hour, minute, 0, 0)
}

function nextRunsForSchedule(schedule, limit = 5) {
  const hour = Number(schedule.hour || 0)
  const minute = Number(schedule.minute || 0)
  if (schedule.trigger_type === 'date') {
    const runAt = localDateTime(schedule.day_of_week, hour, minute)
    return runAt > new Date() ? [runAt] : []
  }
  const allowedDays = new Set(String(schedule.day_of_week || '').split(',').map(d => d.trim().toLowerCase()).filter(Boolean))
  const runs = []
  const cursor = new Date()
  for (let offset = 0; offset < 370 && runs.length < limit; offset += 1) {
    const candidate = new Date(cursor)
    candidate.setDate(cursor.getDate() + offset)
    candidate.setHours(hour, minute, 0, 0)
    if (candidate <= cursor) continue
    if (allowedDays.has(jsDayToScheduleDay(candidate.getDay()))) runs.push(candidate)
  }
  return runs
}

export function buildUpcomingFromSchedules(schedules, limit = 5) {
  const events = []
  schedules.filter(s => s.status === 'active').forEach(schedule => {
    nextRunsForSchedule(schedule, limit).forEach(runAt => {
      events.push({ ...schedule, next_run_at: runAt.toISOString(), upcoming_id: `${schedule.id}_${runAt.toISOString()}` })
    })
  })
  return events.sort((a, b) => new Date(a.next_run_at) - new Date(b.next_run_at)).slice(0, limit)
}
