import numpy as np

from devito import (Grid, Function, TimeFunction, Eq, Operator, norm)
from examples.seismic import RickerSource, TimeAxis

space_order = 8
dtype = np.float32
npad = 20
qmin = 0.1
qmax = 1000.0
fpeak = 0.010
omega = 2.0 * np.pi * fpeak

shape = (1201, 1201, 601)
spacing = (10.0, 10.0, 10.0)
origin = tuple([0.0 for s in shape])
extent = tuple([d * (s - 1) for s, d in zip(shape, spacing)])
grid = Grid(extent=extent, shape=shape, origin=origin, dtype=dtype)

b = Function(name='b', grid=grid, space_order=space_order)
vel = Function(name='vel', grid=grid, space_order=space_order)
wOverQ = Function(name='wOverQ', grid=vel.grid, space_order=space_order)

b.data[:] = 1.0
vel.data[:] = 1.5
wOverQ.data[:] = 1.0

t0 = 0.0
t1 = 250.0
dt = 1.0
time_axis = TimeAxis(start=t0, stop=t1, step=dt)

p0 = TimeFunction(name='p0', grid=grid, time_order=2, space_order=space_order)
t, x, y, z = p0.dimensions

src_coords = np.empty((1, len(shape)), dtype=dtype)
# src_coords[0, :] = [d * (s-1)//2 for d, s in zip(spacing, shape)]
src_coords[0, :] = [d * (s-1)//2 + 100 for d, s in zip(spacing, shape)]
src = RickerSource(name='src', grid=vel.grid, f0=fpeak, npoint=1, time_range=time_axis)
src.coordinates.data[:] = src_coords[:]
src_term = src.inject(field=p0.forward, expr=src * t.spacing**2 * vel**2 / b)


def g1(field):
    return field.dx(x0=x+x.spacing/2)


def g2(field):
    return field.dy(x0=y+y.spacing/2)


def g3(field):
    return field.dz(x0=z+z.spacing/2)


def g1_tilde(field):
    return field.dx(x0=x-x.spacing/2)


def g2_tilde(field):
    return field.dy(x0=y-y.spacing/2)


def g3_tilde(field):
    return field.dz(x0=z-z.spacing/2)


# Time update equation for quasi-P state variable p
update_p = t.spacing**2 * vel**2 / b * \
    (g1_tilde(b * g1(p0)) + g2_tilde(b * g2(p0)) + g3_tilde(b * g3(p0))) + \
    (2 - t.spacing * wOverQ) * p0 + \
    (t.spacing * wOverQ - 1) * p0.backward

stencil_p0 = Eq(p0.forward, update_p)

dt = time_axis.step
spacing_map = vel.grid.spacing_map
spacing_map.update({t.spacing: dt})

op = Operator([stencil_p0, src_term],
              subs=spacing_map, name='OpExampleIso')

f = open("operator.iso.c", "w")
print(op, file=f)
f.close()

bx = 19; by = 8; # 7502
# bx = 16; by = 5; # 7742

op.apply(x0_blk0_size=bx, y0_blk0_size=by)

print("")
print("bx,by,norm; %3d %3d %12.6e" % (bx, by, norm(p0)))

print("")
print(time_axis)
print("nx,ny,nz; %5d %5d %5d" % (shape[0], shape[1], shape[2]))

# from mpi4py import MPI
# comm = MPI.COMM_WORLD
# rank = comm.Get_rank()
# ranknorm = np.empty(1, np.float64)
# sumnorm = np.empty(1, np.float64)
# ranknorm[0] = np.linalg.norm(p0.data)**2
# comm.Reduce(ranknorm, sumnorm, op=MPI.SUM, root=0)
# mynorm = np.sqrt(sumnorm[0])
# print("rank,ranknorm,sumnorm,new norm,devito norm; %2d %12.6f %12.6f %12.6f %12.6f" % 
#       (rank, ranknorm[0], sumnorm[0], mynorm, norm(p0)))

