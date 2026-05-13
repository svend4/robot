"""Tests for marketplace.scheduler and the /scheduler REST API."""
from __future__ import annotations

import datetime
from pathlib import Path

import pytest

from marketplace.scheduler import JobRunResult, ScheduledJob, SkillScheduler

UTC = datetime.timezone.utc


def _now() -> datetime.datetime:
    return datetime.datetime.now(UTC)


def _dt(minutes_offset: int = 0) -> datetime.datetime:
    return _now() + datetime.timedelta(minutes=minutes_offset)


def _ts(dt: datetime.datetime) -> str:
    return dt.isoformat(timespec='seconds')


@pytest.fixture()
def sched(tmp_path) -> SkillScheduler:
    return SkillScheduler(tmp_path / 'sched')


def _add(sched, skill='etd.pick', node='r01', interval=30, **kw):
    return sched.add_job(skill_id=skill, node_id=node,
                         interval_minutes=interval, **kw)


# ── ScheduledJob serialisation ────────────────────────────────────────────────

class TestScheduledJob:
    def test_to_dict_keys(self, sched):
        job = _add(sched)
        d = job.to_dict()
        assert set(d) >= {'job_id', 'skill_id', 'node_id', 'schedule_type',
                          'interval_minutes', 'status', 'next_run_at',
                          'run_count', 'created_at'}

    def test_round_trip(self, sched):
        job = _add(sched, skill='etd.inspect')
        job2 = ScheduledJob.from_dict(job.to_dict())
        assert job2.skill_id == 'etd.inspect'
        assert job2.interval_minutes == 30

    def test_from_dict_defaults(self):
        j = ScheduledJob.from_dict({
            'job_id': 'x', 'skill_id': 'a', 'node_id': 'n',
            'station_id': 'ws', 'schedule_type': 'interval',
        })
        assert j.run_count == 0
        assert j.status == 'active'
        assert j.last_run_success is None

    def test_job_run_result_to_dict(self):
        r = JobRunResult(job_id='x', ran_at='2026-01-01T00:00:00+00:00',
                         success=True, duration_ms=500)
        d = r.to_dict()
        assert d['success'] is True
        assert d['duration_ms'] == 500


# ── SkillScheduler — add_job ──────────────────────────────────────────────────

class TestAddJob:
    def test_creates_job(self, sched):
        job = _add(sched)
        assert job.job_id
        assert job.status == 'active'

    def test_interval_sets_next_run(self, sched):
        now = _dt()
        job = sched.add_job('etd.pick', 'r01', interval_minutes=15, _now=now)
        expected = now + datetime.timedelta(minutes=15)
        assert job.next_run_at == expected.isoformat(timespec='seconds')

    def test_once_sets_next_run_to_run_at(self, sched):
        run_at = _ts(_dt(60))
        job = sched.add_job('etd.pick', 'r01', schedule_type='once',
                            run_at=run_at)
        assert job.next_run_at == run_at

    def test_once_without_run_at_raises(self, sched):
        with pytest.raises(ValueError, match='run_at'):
            sched.add_job('etd.pick', 'r01', schedule_type='once')

    def test_invalid_schedule_type_raises(self, sched):
        with pytest.raises(ValueError, match='schedule_type'):
            sched.add_job('etd.pick', 'r01', schedule_type='cron')

    def test_zero_interval_raises(self, sched):
        with pytest.raises(ValueError, match='interval_minutes'):
            sched.add_job('etd.pick', 'r01', interval_minutes=0)

    def test_run_count_starts_at_zero(self, sched):
        assert _add(sched).run_count == 0

    def test_metadata_stored(self, sched):
        job = sched.add_job('etd.pick', 'r01', metadata={'env': 'prod'})
        assert job.metadata['env'] == 'prod'


# ── SkillScheduler — CRUD ─────────────────────────────────────────────────────

class TestSchedulerCRUD:
    def test_get_job_found(self, sched):
        job = _add(sched)
        assert sched.get_job(job.job_id) is not None

    def test_get_job_unknown_none(self, sched):
        assert sched.get_job('ghost') is None

    def test_list_all(self, sched):
        _add(sched, 'etd.a')
        _add(sched, 'etd.b')
        assert len(sched.list_jobs()) == 2

    def test_list_filter_status(self, sched):
        j = _add(sched)
        sched.pause_job(j.job_id)
        assert len(sched.list_jobs(status='active')) == 0
        assert len(sched.list_jobs(status='paused')) == 1

    def test_list_filter_skill(self, sched):
        _add(sched, 'etd.pick')
        _add(sched, 'etd.inspect')
        assert len(sched.list_jobs(skill_id='etd.pick')) == 1

    def test_list_filter_node(self, sched):
        _add(sched, node='r01')
        _add(sched, node='r02')
        assert len(sched.list_jobs(node_id='r01')) == 1

    def test_list_newest_first(self, sched):
        j1 = _add(sched); j1.created_at = '2026-01-01T00:00:00+00:00'
        j2 = _add(sched); j2.created_at = '2026-06-01T00:00:00+00:00'
        sched._flush()
        lst = sched.list_jobs()
        assert lst[0].created_at > lst[-1].created_at

    def test_remove_existing(self, sched):
        job = _add(sched)
        assert sched.remove_job(job.job_id) is True
        assert sched.get_job(job.job_id) is None

    def test_remove_unknown_false(self, sched):
        assert sched.remove_job('ghost') is False

    def test_job_count(self, sched):
        _add(sched)
        _add(sched)
        assert sched.job_count == 2

    def test_persists(self, tmp_path):
        s1 = SkillScheduler(tmp_path / 's')
        job = s1.add_job('etd.pick', 'r01')
        s2 = SkillScheduler(tmp_path / 's')
        assert s2.get_job(job.job_id) is not None

    def test_creates_dir(self, tmp_path):
        s = SkillScheduler(tmp_path / 'a' / 'b')
        s.add_job('etd.pick', 'r01')
        assert (tmp_path / 'a' / 'b' / 'jobs.json').exists()

    def test_corrupt_file_loads_empty(self, tmp_path):
        (tmp_path / 'jobs.json').write_text('not-json')
        s = SkillScheduler(tmp_path)
        assert s.job_count == 0


# ── SkillScheduler — pause / resume ──────────────────────────────────────────

class TestPauseResume:
    def test_pause_active(self, sched):
        job = _add(sched)
        assert sched.pause_job(job.job_id) is True
        assert sched.get_job(job.job_id).status == 'paused'

    def test_pause_paused_false(self, sched):
        job = _add(sched)
        sched.pause_job(job.job_id)
        assert sched.pause_job(job.job_id) is False

    def test_pause_unknown_false(self, sched):
        assert sched.pause_job('ghost') is False

    def test_resume_paused(self, sched):
        job = _add(sched)
        sched.pause_job(job.job_id)
        assert sched.resume_job(job.job_id) is True
        assert sched.get_job(job.job_id).status == 'active'

    def test_resume_active_false(self, sched):
        job = _add(sched)
        assert sched.resume_job(job.job_id) is False

    def test_resume_unknown_false(self, sched):
        assert sched.resume_job('ghost') is False


# ── SkillScheduler — due_jobs ─────────────────────────────────────────────────

class TestDueJobs:
    def test_no_due_when_future(self, sched):
        now = _dt()
        sched.add_job('etd.pick', 'r01', interval_minutes=60, _now=now)
        # next_run_at is 60 min in the future
        assert sched.due_jobs(_now=now) == []

    def test_due_when_past_next_run(self, sched):
        past = _dt(-120)
        job = sched.add_job('etd.pick', 'r01', interval_minutes=30, _now=past)
        # next_run_at = past + 30m = 90 min ago → due
        assert len(sched.due_jobs(_now=_dt())) == 1

    def test_paused_jobs_not_due(self, sched):
        past = _dt(-120)
        job = sched.add_job('etd.pick', 'r01', interval_minutes=30, _now=past)
        sched.pause_job(job.job_id)
        assert sched.due_jobs() == []

    def test_done_jobs_not_due(self, sched):
        past = _dt(-120)
        job = sched.add_job('etd.pick', 'r01', schedule_type='once',
                            run_at=_ts(past), _now=_dt(-180))
        sched.record_run(job.job_id, success=True)
        assert sched.due_jobs() == []

    def test_due_jobs_sorted(self, sched):
        t1 = _dt(-90)
        t2 = _dt(-60)
        j1 = sched.add_job('etd.a', 'r01', interval_minutes=30, _now=t1)
        j2 = sched.add_job('etd.b', 'r01', interval_minutes=30, _now=t2)
        due = sched.due_jobs()
        assert due[0].next_run_at <= due[-1].next_run_at


# ── SkillScheduler — record_run ───────────────────────────────────────────────

class TestRecordRun:
    def test_record_increments_count(self, sched):
        job = _add(sched)
        sched.record_run(job.job_id, success=True)
        assert sched.get_job(job.job_id).run_count == 1

    def test_record_sets_last_run(self, sched):
        job = _add(sched)
        sched.record_run(job.job_id, success=True)
        assert sched.get_job(job.job_id).last_run_at is not None

    def test_record_advances_next_run_interval(self, sched):
        now = _dt()
        job = sched.add_job('etd.pick', 'r01', interval_minutes=15, _now=now)
        sched.record_run(job.job_id, success=True, _now=now)
        expected = (now + datetime.timedelta(minutes=15)).isoformat(timespec='seconds')
        assert sched.get_job(job.job_id).next_run_at == expected

    def test_record_once_job_becomes_done(self, sched):
        job = sched.add_job('etd.pick', 'r01', schedule_type='once',
                            run_at=_ts(_dt(-10)))
        sched.record_run(job.job_id, success=True)
        assert sched.get_job(job.job_id).status == 'done'
        assert sched.get_job(job.job_id).next_run_at is None

    def test_record_sets_last_run_success(self, sched):
        job = _add(sched)
        sched.record_run(job.job_id, success=False)
        assert sched.get_job(job.job_id).last_run_success is False

    def test_record_returns_result(self, sched):
        job = _add(sched)
        result = sched.record_run(job.job_id, success=True, duration_ms=500)
        assert isinstance(result, JobRunResult)
        assert result.success is True
        assert result.duration_ms == 500

    def test_record_unknown_returns_none(self, sched):
        assert sched.record_run('ghost', success=True) is None


# ── REST API /scheduler ───────────────────────────────────────────────────────

import api.scheduler as _sched_mod


@pytest.fixture(autouse=True)
def patch_sched_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(_sched_mod, '_SCHED_DIR', tmp_path / 'sched')


@pytest.fixture()
def api_client():
    from api.app import app
    from fastapi.testclient import TestClient
    return TestClient(app)


def _job_body(**kw):
    body = {'skill_id': 'etd.pick', 'node_id': 'r01', 'interval_minutes': 30}
    body.update(kw)
    return body


class TestSchedulerApiCreate:
    def test_create_201(self, api_client):
        r = api_client.post('/scheduler/jobs', json=_job_body())
        assert r.status_code == 201

    def test_create_has_job_id(self, api_client):
        data = api_client.post('/scheduler/jobs', json=_job_body()).json()
        assert 'job_id' in data
        assert data['status'] == 'active'

    def test_once_missing_run_at_422(self, api_client):
        r = api_client.post('/scheduler/jobs',
                            json=_job_body(schedule_type='once'))
        assert r.status_code == 422


class TestSchedulerApiList:
    def test_list_200(self, api_client):
        assert api_client.get('/scheduler/jobs').status_code == 200

    def test_list_empty(self, api_client):
        data = api_client.get('/scheduler/jobs').json()
        assert data['count'] == 0

    def test_list_after_create(self, api_client):
        api_client.post('/scheduler/jobs', json=_job_body())
        assert api_client.get('/scheduler/jobs').json()['count'] == 1

    def test_list_filter_status(self, api_client):
        api_client.post('/scheduler/jobs', json=_job_body())
        assert api_client.get('/scheduler/jobs?status=active').json()['count'] == 1
        assert api_client.get('/scheduler/jobs?status=paused').json()['count'] == 0


class TestSchedulerApiGet:
    def test_get_found(self, api_client):
        job_id = api_client.post('/scheduler/jobs',
                                  json=_job_body()).json()['job_id']
        r = api_client.get(f'/scheduler/jobs/{job_id}')
        assert r.status_code == 200
        assert r.json()['job_id'] == job_id

    def test_get_404(self, api_client):
        assert api_client.get('/scheduler/jobs/ghost').status_code == 404


class TestSchedulerApiDelete:
    def test_delete_200(self, api_client):
        job_id = api_client.post('/scheduler/jobs',
                                  json=_job_body()).json()['job_id']
        r = api_client.delete(f'/scheduler/jobs/{job_id}')
        assert r.status_code == 200
        assert r.json()['removed'] == job_id

    def test_delete_404(self, api_client):
        assert api_client.delete('/scheduler/jobs/ghost').status_code == 404


class TestSchedulerApiLifecycle:
    def _create(self, api_client) -> str:
        return api_client.post('/scheduler/jobs',
                               json=_job_body()).json()['job_id']

    def test_pause_200(self, api_client):
        job_id = self._create(api_client)
        r = api_client.put(f'/scheduler/jobs/{job_id}/pause')
        assert r.status_code == 200
        assert r.json()['status'] == 'paused'

    def test_pause_already_paused_409(self, api_client):
        job_id = self._create(api_client)
        api_client.put(f'/scheduler/jobs/{job_id}/pause')
        assert api_client.put(f'/scheduler/jobs/{job_id}/pause').status_code == 409

    def test_pause_404(self, api_client):
        assert api_client.put('/scheduler/jobs/ghost/pause').status_code == 404

    def test_resume_200(self, api_client):
        job_id = self._create(api_client)
        api_client.put(f'/scheduler/jobs/{job_id}/pause')
        r = api_client.put(f'/scheduler/jobs/{job_id}/resume')
        assert r.status_code == 200
        assert r.json()['status'] == 'active'

    def test_resume_active_409(self, api_client):
        job_id = self._create(api_client)
        assert api_client.put(f'/scheduler/jobs/{job_id}/resume').status_code == 409


class TestSchedulerApiDue:
    def test_due_200(self, api_client):
        assert api_client.get('/scheduler/due').status_code == 200

    def test_due_empty_initially(self, api_client):
        api_client.post('/scheduler/jobs', json=_job_body(interval_minutes=60))
        data = api_client.get('/scheduler/due').json()
        assert data['count'] == 0  # next_run is in future


class TestSchedulerApiRun:
    def test_record_run_200(self, api_client):
        job_id = api_client.post('/scheduler/jobs',
                                  json=_job_body()).json()['job_id']
        r = api_client.post(f'/scheduler/jobs/{job_id}/run',
                             json={'success': True, 'duration_ms': 300})
        assert r.status_code == 200
        assert r.json()['success'] is True

    def test_record_run_increments(self, api_client):
        job_id = api_client.post('/scheduler/jobs',
                                  json=_job_body()).json()['job_id']
        api_client.post(f'/scheduler/jobs/{job_id}/run', json={'success': True})
        data = api_client.get(f'/scheduler/jobs/{job_id}').json()
        assert data['run_count'] == 1

    def test_record_run_404(self, api_client):
        r = api_client.post('/scheduler/jobs/ghost/run', json={'success': True})
        assert r.status_code == 404
